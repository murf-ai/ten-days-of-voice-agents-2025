# backend/src/agent.py
import logging
import json
import os
import time
from datetime import datetime
from typing import List, Dict, Optional

from dotenv import load_dotenv

from livekit.agents import (
    Agent,
    AgentSession,
    JobContext,
    JobProcess,
    RoomInputOptions,
    WorkerOptions,
    cli,
    tokenize,
    function_tool,
    RunContext,
)
from livekit.plugins import murf, deepgram, google, silero, noise_cancellation
from livekit.plugins.turn_detector.multilingual import MultilingualModel

load_dotenv(".env.local")
logger = logging.getLogger("food-agent")

# Base paths: place order files in backend/order_details/
BASE_DIR = os.path.dirname(__file__)  # backend/src
PROJECT_ROOT = os.path.abspath(os.path.join(BASE_DIR, ".."))  # backend
ORDER_DIR = os.path.join(PROJECT_ROOT, "order_details")

# ensure folder exists
os.makedirs(ORDER_DIR, exist_ok=True)

CATALOG_PATH = os.path.join(ORDER_DIR, "catalog.json")
ORDERS_PATH = os.path.join(ORDER_DIR, "orders.json")


# -------------------------
# Helpers for file IO
# -------------------------
def load_json(path: str, default):
    """Load JSON; return default if not found or parse fails."""
    if not os.path.exists(path):
        # create default file on first load attempt
        try:
            save_json(path, default)
        except Exception:
            # fall through and return default
            pass
        return default

    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error loading JSON {path}: {e}")
        return default


def save_json(path: str, data, retries: int = 5, retry_delay: float = 0.05) -> bool:
    """Save JSON to `path` with small retry loop to handle Windows file locks."""
    for attempt in range(retries):
        try:
            # ensure parent dir exists
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            return True
        except PermissionError as e:
            logger.warning(f"PermissionError writing {path}, retrying... ({attempt+1}/{retries})")
            time.sleep(retry_delay)
        except Exception as e:
            logger.error(f"Error saving JSON {path}: {e}")
            return False
    logger.error(f"Failed to write JSON {path} after {retries} retries.")
    return False


# -------------------------
# Default catalog (created if missing)
# -------------------------
DEFAULT_CATALOG = {
    "Groceries": [
        {"name": "apple", "price": 10, "unit": "each"},
        {"name": "banana", "price": 5, "unit": "each"},
        {"name": "bread", "price": 30, "unit": "loaf"},
        {"name": "milk", "price": 45, "unit": "litre"},
        {"name": "eggs", "price": 60, "unit": "dozen"},
    ],
    "Snacks": [
        {"name": "chips", "price": 20},
        {"name": "cookies", "price": 25}
    ],
    "PreparedFood": [
        {"name": "sandwich", "price": 50},
        {"name": "pasta", "price": 120}
    ],
    "Recipes": {
        "peanut butter sandwich": ["bread", "peanut butter"],
        "pasta plate": ["pasta", "tomato sauce"]
    }
}

# Ensure files exist (catalog initialized with default if missing, orders starts as empty list)
if not os.path.exists(CATALOG_PATH):
    logger.info(f"catalog.json missing — creating default at {CATALOG_PATH}")
    save_json(CATALOG_PATH, DEFAULT_CATALOG)

if not os.path.exists(ORDERS_PATH):
    save_json(ORDERS_PATH, [])


# -------------------------
# Agent
# -------------------------
class FoodAgent(Agent):
    def __init__(self):
        instructions = """
        You are a friendly food & grocery ordering assistant. Offer concise confirmations, read items and totals clearly,
        and use the provided tools to modify cart state or place orders.
        If the user wants ingredients for a recipe, use the get_ingredients_for_dish tool.
        """
        super().__init__(instructions=instructions)

        # Load catalog (categories, items, recipes)
        self.catalog = load_json(CATALOG_PATH, default=DEFAULT_CATALOG)
        # cart is a list of dicts: {"name": str, "qty": int, "price": float}
        self.cart: List[Dict] = []

    # -------------------------
    # Utility methods (internal)
    # -------------------------
    def _find_item_in_catalog(self, item_name: str) -> Optional[Dict]:
        name = item_name.strip().lower()
        # catalog may contain categories and direct lists
        for cat_key, items in self.catalog.items():
            # recipes is handled separately
            if cat_key.lower() == "recipes":
                continue
            if isinstance(items, list):
                for it in items:
                    if it.get("name", "").lower() == name:
                        return {"name": it["name"], "price": it.get("price", 0)}
        return None

    def _cart_index(self, item_name: str) -> Optional[int]:
        for i, it in enumerate(self.cart):
            if it["name"].lower() == item_name.strip().lower():
                return i
        return None

    def _cart_total(self) -> float:
        return sum(item["qty"] * item.get("price", 0) for item in self.cart)

    # -------------------------
    # Tools (exposed to LLM via function_tool)
    # -------------------------
    @function_tool
    async def add_to_cart(self, ctx: RunContext, item_name: str, quantity: int = 1) -> str:
        """Add an item from the catalog to the cart."""
        if quantity <= 0:
            return "Please provide a positive quantity."

        item = self._find_item_in_catalog(item_name)
        if not item:
            return f"Item '{item_name}' not found in the catalog."

        idx = self._cart_index(item["name"])
        if idx is not None:
            self.cart[idx]["qty"] += quantity
        else:
            self.cart.append({"name": item["name"], "qty": quantity, "price": item.get("price", 0)})

        return f"Added {quantity} × {item['name']} to your cart."

    @function_tool
    async def remove_from_cart(self, ctx: RunContext, item_name: str, quantity: int = 0) -> str:
        """Remove an item or reduce quantity. If quantity <= 0 remove whole item."""
        idx = self._cart_index(item_name)
        if idx is None:
            return f"Item '{item_name}' is not in your cart."

        if quantity <= 0 or quantity >= self.cart[idx]["qty"]:
            removed = self.cart.pop(idx)
            return f"Removed all {removed['name']} from your cart."
        else:
            self.cart[idx]["qty"] -= quantity
            return f"Removed {quantity} × {self.cart[idx]['name']} from your cart."

    @function_tool
    async def view_cart(self, ctx: RunContext) -> str:
        """Return a readable summary of the cart."""
        if not self.cart:
            return "Your cart is empty."
        lines = []
        for it in self.cart:
            price = it.get("price", 0)
            lines.append(f"{it['qty']} × {it['name']} @ {price} each = {it['qty'] * price}")
        total = self._cart_total()
        lines.append(f"Total: {total}")
        return "\n".join(lines)

    @function_tool
    async def get_ingredients_for_dish(self, ctx: RunContext, dish_name: str) -> str:
        """Look up recipe ingredients in catalog.recipes and add them to the cart."""
        recipes = self.catalog.get("Recipes", {})
        key = dish_name.strip().lower()
        # recipes keys could be stored lowercase or original; try both
        found_key = None
        for k in recipes.keys():
            if k.lower() == key:
                found_key = k
                break

        if not found_key:
            return f"Recipe for '{dish_name}' not found."

        ingredients = recipes[found_key]  # list of ingredient names
        added_items = []
        for ing in ingredients:
            item = self._find_item_in_catalog(ing)
            if item:
                # add 1 by default
                idx = self._cart_index(item["name"])
                if idx is not None:
                    self.cart[idx]["qty"] += 1
                else:
                    self.cart.append({"name": item["name"], "qty": 1, "price": item.get("price", 0)})
                added_items.append(item["name"])
            else:
                # If ingredient not in catalog, still note it
                added_items.append(f"{ing} (not in catalog)")

        return f"Added ingredients for {found_key}: {', '.join(added_items)}"

    @function_tool
    async def place_order(self, ctx: RunContext, user_name: str = "anonymous") -> str:
        """Place the order: write it to orders.json and clear the cart."""
        if not self.cart:
            return "Your cart is empty. Add items before placing an order."

        # Prepare order
        order = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "user": user_name,
            "items": self.cart.copy(),
            "total": self._cart_total(),
        }

        # Load existing orders and append
        orders = load_json(ORDERS_PATH, default=[])
        if not isinstance(orders, list):
            orders = []

        orders.append(order)
        saved = save_json(ORDERS_PATH, orders)
        if saved:
            # Clear cart after successful save
            self.cart = []
            return f"Order placed successfully. Total: {order['total']}. Saved to {ORDERS_PATH}."
        else:
            return "Failed to save the order. Please try again."

    # optional helper tool to list catalog categories/items
    @function_tool
    async def list_catalog(self, ctx: RunContext) -> str:
        """Return a short summary of catalog categories and items."""
        lines = []
        for cat, items in self.catalog.items():
            if cat.lower() == "recipes":
                lines.append(f"{cat}: {', '.join(items.keys())}")
            elif isinstance(items, list):
                names = [it.get("name", "") for it in items]
                lines.append(f"{cat}: {', '.join(names)}")
        return "\n".join(lines)


# -------------------------
# Prewarm
# -------------------------
def prewarm(proc: JobProcess):
    proc.userdata["vad"] = silero.VAD.load()


# -------------------------
# Entrypoint
# -------------------------
async def entrypoint(ctx: JobContext):
    ctx.log_context_fields = {"room": ctx.room.name}

    # Ensure catalog exists; if not, create a minimal default
    if not os.path.exists(CATALOG_PATH):
        default_catalog = DEFAULT_CATALOG
        save_json(CATALOG_PATH, default_catalog)
        logger.info(f"Created default catalog at {CATALOG_PATH}")

    # Create agent and session
    agent = FoodAgent()

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

    await session.start(
        agent=agent,
        room=ctx.room,
        room_input_options=RoomInputOptions(
            noise_cancellation=noise_cancellation.BVC(),
        ),
    )

    await ctx.connect()

    # Greet the user — use current API
    await session.say("Hello! I'm your Food & Grocery Assistant. How can I help you today?")


# -------------------------
# Main
# -------------------------
if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint, prewarm_fnc=prewarm))
