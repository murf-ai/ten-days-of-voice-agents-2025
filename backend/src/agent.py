import logging
import json
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional

from dotenv import load_dotenv
from livekit.agents import (
    Agent,
    AgentSession,
    JobContext,
    JobProcess,
    MetricsCollectedEvent,
    RoomInputOptions,
    WorkerOptions,
    cli,
    metrics,
    tokenize,
    function_tool,
    RunContext,
)
from livekit.plugins import murf, silero, google, deepgram, noise_cancellation
from livekit.plugins.turn_detector.multilingual import MultilingualModel

logger = logging.getLogger("agent")

load_dotenv(".env.local")

# ------------- Helpers: load catalog & orders file -------------


def load_catalog() -> List[Dict[str, Any]]:
    base_dir = Path(__file__).resolve().parent.parent  # backend/
    path = base_dir / "shared-data" / "day7_catalog.json"
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, list):
                return data
    except Exception as e:
        logger.warning(f"Failed to load day7_catalog.json: {e}")
    return []


def load_orders() -> List[Dict[str, Any]]:
    base_dir = Path(__file__).resolve().parent.parent  # backend/
    path = base_dir / "orders" / "day7_orders.json"
    if not path.exists():
        return []
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, list):
                return data
    except Exception as e:
        logger.warning(f"Failed to load day7_orders.json: {e}")
    return []


def save_orders(orders: List[Dict[str, Any]]) -> None:
    base_dir = Path(__file__).resolve().parent.parent  # backend/
    orders_dir = base_dir / "orders"
    orders_dir.mkdir(parents=True, exist_ok=True)
    path = orders_dir / "day7_orders.json"
    with path.open("w", encoding="utf-8") as f:
        json.dump(orders, f, indent=2, ensure_ascii=False)


class FalconMartAgent(Agent):
    def __init__(self, catalog: List[Dict[str, Any]]) -> None:
        self.catalog = catalog
        self.cart: List[Dict[str, Any]] = []  # each: {item_id, name, unit_price, quantity, unit}
        self.brand_name = "FalconMart"

        # Simple recipe mapping for "ingredients for X"
        # recipe_name (lowercase) -> list of item IDs
        self.recipes = {
            "peanut butter sandwich": ["bread_whole_wheat", "peanut_butter"],
            "pasta for two": ["pasta_penni", "pasta_sauce"],
            "simple breakfast": ["bread_whole_wheat", "eggs_6", "milk_toned"],
        }

        instructions = f"""
You are a friendly voice ordering assistant for {self.brand_name}, a fictional food & grocery delivery store.

Your job:
- Help the user order groceries, snacks, fruits, and simple prepared food.
- Use the available tools to manage a shopping cart.
- When the user is done, place the order and save it using the tools.

Capabilities:
1. Greet the user and briefly explain what you can do.
   Example: "Hi, I'm your FalconMart ordering assistant. I can help you add groceries, snacks, and ingredients for simple meals to your cart."

2. Ask clarifying questions:
   - If the user just says "bread" but the catalog has one bread item, you can assume that one.
   - If there are multiple matching items, ask which they mean:
     brand, size, or category.

3. Cart management:
   - Use the tools:
     * `add_item_to_cart` to add items.
     * `update_item_quantity` to change quantities.
     * `remove_item_from_cart` to remove items.
     * `list_cart` to show current cart contents.
   - Confirm important actions in a natural sentence:
     "I've added 2 packs of salted potato chips to your cart."

4. Handle "ingredients for X" style requests:
   - When the user says things like:
     * "I need ingredients for a peanut butter sandwich."
     * "Get me what I need for pasta for two people."
   - Call `add_ingredients_for_recipe` with a recipe name like:
     "peanut butter sandwich", "pasta for two", or "simple breakfast".
   - After the tool returns, clearly say what you added.

5. Placing the order:
   - When the user says "That's all", "Place my order", or "I'm done":
     * First, confirm the final cart and the total amount.
     * Ask for a simple name and address (as plain text).
     * Then call the `place_order` tool to save the order to JSON.
   - After placing the order, confirm:
     "Your order has been placed and saved. You can now close this session."

Important constraints:
- You must NOT invent items that are not in the catalog. If something is not available, say so.
- Do not talk about tools, JSON, or internal implementation.
- Keep answers short, natural, and helpful.
- If the cart is empty and the user tries to place an order, gently say that the cart is empty and ask what they want to add.
"""
        super().__init__(instructions=instructions)

    # ------------ Internal helpers ------------

    def _find_catalog_items(self, name_or_keyword: str) -> List[Dict[str, Any]]:
        """
        Very simple keyword-based search in catalog by name and tags.
        """
        query = name_or_keyword.strip().lower()
        if not query:
            return []

        matches: List[Dict[str, Any]] = []
        for item in self.catalog:
            text = (item.get("name", "") + " " + " ".join(item.get("tags", []))).lower()
            if query in text:
                matches.append(item)
        return matches

    def _find_cart_line(self, item_id: str) -> Optional[Dict[str, Any]]:
        for line in self.cart:
            if line.get("item_id") == item_id:
                return line
        return None

    # ------------ Tools ------------

    @function_tool()
    async def add_item_to_cart(
        self,
        context: RunContext,
        item_name: str,
        quantity: int = 1,
    ) -> str:
        """
        Add an item from the catalog to the cart.

        Args:
            item_name: A keyword or item name, e.g. "bread", "peanut butter".
            quantity: How many units to add.
        """
        matches = self._find_catalog_items(item_name)
        if not matches:
            return f"I couldn't find any item matching '{item_name}' in the catalog."

        # If multiple matches, pick the first one for now.
        item = matches[0]
        item_id = item["id"]
        name = item["name"]
        unit_price = item["price"]
        unit = item.get("unit", "")

        if quantity <= 0:
            quantity = 1

        existing = self._find_cart_line(item_id)
        if existing:
            existing["quantity"] += quantity
        else:
            self.cart.append(
                {
                    "item_id": item_id,
                    "name": name,
                    "unit_price": unit_price,
                    "unit": unit,
                    "quantity": quantity,
                }
            )

        logger.info(f"[Cart] Added {quantity} x {name} ({item_id})")
        return f"Added {quantity} x {name} to your cart."

    @function_tool()
    async def update_item_quantity(
        self,
        context: RunContext,
        item_name: str,
        quantity: int,
    ) -> str:
        """
        Update the quantity of an item in the cart. If quantity is 0, item is removed.
        """
        matches = self._find_catalog_items(item_name)
        if not matches:
            return f"I couldn't find any item matching '{item_name}' in the catalog."

        item = matches[0]
        item_id = item["id"]
        line = self._find_cart_line(item_id)
        if not line:
            return f"{item['name']} is not currently in your cart."

        if quantity <= 0:
            self.cart = [l for l in self.cart if l.get("item_id") != item_id]
            logger.info(f"[Cart] Removed {item['name']} ({item_id}) from cart.")
            return f"Removed {item['name']} from your cart."

        line["quantity"] = quantity
        logger.info(f"[Cart] Updated {item['name']} ({item_id}) quantity to {quantity}.")
        return f"Updated {item['name']} quantity to {quantity}."

    @function_tool()
    async def remove_item_from_cart(
        self,
        context: RunContext,
        item_name: str,
    ) -> str:
        """
        Remove an item completely from the cart.
        """
        matches = self._find_catalog_items(item_name)
        if not matches:
            return f"I couldn't find any item matching '{item_name}' in the catalog."

        item = matches[0]
        item_id = item["id"]
        before_len = len(self.cart)
        self.cart = [l for l in self.cart if l.get("item_id") != item_id]
        after_len = len(self.cart)

        if before_len == after_len:
            return f"{item['name']} is not currently in your cart."
        logger.info(f"[Cart] Removed {item['name']} ({item_id}) from cart.")
        return f"Removed {item['name']} from your cart."

    @function_tool()
    async def list_cart(
        self,
        context: RunContext,
    ) -> str:
        """
        Return a human-readable summary of the current cart and total.
        """
        if not self.cart:
            return "Your cart is currently empty."

        lines = []
        total = 0
        for line in self.cart:
            name = line["name"]
            qty = line["quantity"]
            price = line["unit_price"]
            unit = line.get("unit", "")
            line_total = qty * price
            total += line_total
            lines.append(f"{qty} x {name} ({unit}) → ₹{line_total}")

        summary = "Here is your current cart:\n" + "\n".join(lines) + f"\nTotal so far: ₹{total}"
        return summary

    @function_tool()
    async def add_ingredients_for_recipe(
        self,
        context: RunContext,
        recipe_name: str,
    ) -> str:
        """
        Add multiple catalog items for a simple recipe, like 'peanut butter sandwich' or 'pasta for two'.
        """
        key = recipe_name.strip().lower()
        if key not in self.recipes:
            return (
                "I don't have a recipe saved for that yet. "
                "Right now I know recipes like peanut butter sandwich, pasta for two, and simple breakfast."
            )

        item_ids = self.recipes[key]
        added_items: List[str] = []
        for item_id in item_ids:
            item = next((i for i in self.catalog if i.get("id") == item_id), None)
            if not item:
                continue
            existing = self._find_cart_line(item_id)
            if existing:
                existing["quantity"] += 1
            else:
                self.cart.append(
                    {
                        "item_id": item["id"],
                        "name": item["name"],
                        "unit_price": item["price"],
                        "unit": item.get("unit", ""),
                        "quantity": 1,
                    }
                )
            added_items.append(item["name"])

        if not added_items:
            return "I couldn't find the items for that recipe in the catalog."

        logger.info(f"[Cart] Recipe '{recipe_name}' added items: {added_items}")
        return (
            f"I've added the ingredients for {recipe_name}: " + ", ".join(added_items) + "."
        )

    @function_tool()
    async def place_order(
        self,
        context: RunContext,
        customer_name: str,
        address: str,
    ) -> str:
        """
        Place the current order: compute total, save to JSON, and clear the cart.

        Args:
            customer_name: Name of the customer for the order.
            address: Delivery address as free text.
        """
        if not self.cart:
            return "Your cart is empty, so I can't place an order yet."

        orders = load_orders()
        order_id = f"ORD{len(orders) + 1:04d}"

        items = []
        total = 0
        for line in self.cart:
            line_total = line["quantity"] * line["unit_price"]
            total += line_total
            items.append(
                {
                    "item_id": line["item_id"],
                    "name": line["name"],
                    "unit": line.get("unit", ""),
                    "unit_price": line["unit_price"],
                    "quantity": line["quantity"],
                    "line_total": line_total,
                }
            )

        order = {
            "order_id": order_id,
            "customer_name": customer_name,
            "address": address,
            "items": items,
            "total": total,
            "status": "received",
            "timestamp": datetime.utcnow().isoformat(),
        }

        orders.append(order)
        save_orders(orders)

        logger.info(f"[Order] Placed order {order_id} for {customer_name}, total ₹{total}.")
        # Clear the cart after placing order
        self.cart = []

        return (
            f"Your order {order_id} has been placed for a total of ₹{total}. "
            "It has been saved in our system and marked as received."
        )


# ----------------------- Session Setup -----------------------


def prewarm(proc: JobProcess):
    proc.userdata["vad"] = silero.VAD.load()


async def entrypoint(ctx: JobContext):
    ctx.log_context_fields = {"room": ctx.room.name}

    catalog = load_catalog()
    logger.info(f"Day 7 FalconMart – loaded {len(catalog)} catalog items.")

    session = AgentSession(
        stt=deepgram.STT(model="nova-3"),
        llm=google.LLM(model="gemini-2.5-flash"),
        tts=murf.TTS(
            voice="en-US-matthew",
            style="Conversation",
            tokenizer=tokenize.basic.SentenceTokenizer(min_sentence_len=2),
            text_pacing=True,
        ),
        turn_detection=MultilingualModel(),
        vad=ctx.proc.userdata["vad"],
        preemptive_generation=True,
    )

    usage_collector = metrics.UsageCollector()

    @session.on("metrics_collected")
    def _on_metrics_collected(ev: MetricsCollectedEvent):
        metrics.log_metrics(ev.metrics)
        usage_collector.collect(ev.metrics)

    async def log_usage():
        summary = usage_collector.get_summary()
        logger.info(f"Usage: {summary}")

    ctx.add_shutdown_callback(log_usage)

    await session.start(
        agent=FalconMartAgent(catalog=catalog),
        room=ctx.room,
        room_input_options=RoomInputOptions(
            noise_cancellation=noise_cancellation.BVC(),
        ),
    )

    await ctx.connect()


if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint, prewarm_fnc=prewarm))
