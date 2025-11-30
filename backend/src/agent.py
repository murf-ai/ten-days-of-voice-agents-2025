# agent.py
"""
Voice E-commerce Shopping Assistant — Implementation for Day 9 with ACP-inspired design:
- Product catalog with filtering
- Order creation and persistence
- Voice-driven shopping flow
- Simple order history

Patched so all function tools accept flexible payloads to avoid Pydantic "Field required" errors.
"""
import logging
import os
import json
import uuid
import asyncio
from datetime import datetime
from typing import List, Dict, Optional
from dotenv import load_dotenv

from livekit.agents import (
    Agent,
    AgentSession,
    JobContext,
    JobProcess,
    RunContext,
    RoomInputOptions,
    WorkerOptions,
    cli,
    function_tool,
)
from livekit.plugins import murf, silero, google, deepgram, noise_cancellation
from livekit.plugins.turn_detector.multilingual import MultilingualModel

logger = logging.getLogger("shopping_assistant")
load_dotenv(".env.local")

# ------------------- Storage paths -------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(os.path.dirname(BASE_DIR), "shared-data")
os.makedirs(DATA_DIR, exist_ok=True)
ORDERS_PATH = os.path.join(DATA_DIR, "orders.json")

# Ensure orders file exists
if not os.path.exists(ORDERS_PATH):
    with open(ORDERS_PATH, "w", encoding="utf-8") as f:
        json.dump([], f, indent=2)

# ------------------- Product Catalog -------------------
PRODUCTS = [
    {
        "id": "mug-001",
        "name": "Stoneware Coffee Mug",
        "description": "Handcrafted ceramic mug perfect for your morning coffee",
        "price": 800,
        "currency": "INR",
        "category": "mug",
        "color": "white",
        "in_stock": True,
        "attributes": {"material": "ceramic", "capacity_ml": 350}
    },
    {
        "id": "mug-002",
        "name": "Blue Enamel Camping Mug",
        "description": "Durable enamel mug for outdoor adventures",
        "price": 650,
        "currency": "INR",
        "category": "mug",
        "color": "blue",
        "in_stock": True,
        "attributes": {"material": "enamel", "capacity_ml": 400}
    },
    {
        "id": "mug-003",
        "name": "Premium Coffee Mug Set",
        "description": "Set of 4 elegant coffee mugs with saucers",
        "price": 1200,
        "currency": "INR",
        "category": "mug",
        "color": "brown",
        "in_stock": True,
        "attributes": {"material": "porcelain", "capacity_ml": 300, "set_size": 4}
    },
    {
        "id": "tshirt-001",
        "name": "Cotton Crew Neck T-Shirt",
        "description": "Soft 100% cotton t-shirt for everyday wear",
        "price": 450,
        "currency": "INR",
        "category": "clothing",
        "color": "black",
        "size": "M",
        "in_stock": True,
        "attributes": {"material": "cotton", "sleeve": "short"}
    },
    {
        "id": "tshirt-002",
        "name": "Premium Organic T-Shirt",
        "description": "Eco-friendly organic cotton t-shirt",
        "price": 850,
        "currency": "INR",
        "category": "clothing",
        "color": "white",
        "size": "L",
        "in_stock": True,
        "attributes": {"material": "organic_cotton", "sleeve": "short"}
    },
    {
        "id": "hoodie-001",
        "name": "Classic Fleece Hoodie",
        "description": "Warm and comfortable fleece hoodie",
        "price": 1200,
        "currency": "INR",
        "category": "clothing",
        "color": "black",
        "size": "M",
        "in_stock": True,
        "attributes": {"material": "fleece", "hood": "yes", "pocket": "kangaroo"}
    },
    {
        "id": "hoodie-002",
        "name": "Sport Tech Hoodie",
        "description": "Lightweight technical hoodie for active wear",
        "price": 1800,
        "currency": "INR",
        "category": "clothing",
        "color": "navy",
        "size": "L",
        "in_stock": True,
        "attributes": {"material": "polyester", "hood": "yes", "moisture_wicking": "yes"}
    }
]

# ------------------- Commerce Logic (ACP-inspired) -------------------


def list_products(filters: Optional[Dict] = None, search_term: Optional[str] = None) -> List[Dict]:
    """Filter products based on criteria - ACP-inspired catalog browsing"""
    filtered_products = PRODUCTS.copy()

    if filters:
        # Apply filters
        if "category" in filters:
            filtered_products = [p for p in filtered_products if p["category"] == filters["category"]]

        if "max_price" in filters:
            filtered_products = [p for p in filtered_products if p["price"] <= filters["max_price"]]

        if "color" in filters:
            filtered_products = [p for p in filtered_products if p.get("color") == filters["color"]]

        if "in_stock" in filters:
            filtered_products = [p for p in filtered_products if p["in_stock"] == filters["in_stock"]]

    # Apply search term if provided
    if search_term:
        search_lower = search_term.lower()
        filtered_products = [
            p for p in filtered_products
            if (search_lower in p["name"].lower() or
                search_lower in p["description"].lower() or
                search_lower in p["category"].lower())
        ]

    return filtered_products


def create_order(line_items: List[Dict]) -> Dict:
    """Create an order - ACP-inspired order creation"""
    # Load existing orders
    try:
        with open(ORDERS_PATH, "r", encoding="utf-8") as f:
            orders = json.load(f)
    except:
        orders = []

    # Calculate order total and validate products
    total = 0
    order_items = []

    for item in line_items:
        product = next((p for p in PRODUCTS if p["id"] == item["product_id"]), None)
        if not product:
            raise ValueError(f"Product {item['product_id']} not found")

        if not product["in_stock"]:
            raise ValueError(f"Product {product['name']} is out of stock")

        quantity = item.get("quantity", 1)
        item_total = product["price"] * quantity

        order_items.append({
            "product_id": product["id"],
            "name": product["name"],
            "quantity": quantity,
            "unit_price": product["price"],
            "currency": product["currency"],
            "item_total": item_total
        })

        total += item_total

    # Create order object
    order = {
        "id": str(uuid.uuid4()),
        "created_at": datetime.utcnow().isoformat() + "Z",
        "status": "CONFIRMED",
        "items": order_items,
        "total": total,
        "currency": "INR",
        "buyer": {"name": "Voice Customer"}  # Simplified buyer info
    }

    # Save order
    orders.append(order)
    with open(ORDERS_PATH, "w", encoding="utf-8") as f:
        json.dump(orders, f, indent=2, ensure_ascii=False)

    return order


def get_order_history(limit: Optional[int] = None) -> List[Dict]:
    """Get order history - ACP-inspired order queries"""
    try:
        with open(ORDERS_PATH, "r", encoding="utf-8") as f:
            orders = json.load(f)
    except:
        orders = []

    # Sort by creation date, newest first
    orders.sort(key=lambda x: x.get("created_at", ""), reverse=True)

    if limit:
        orders = orders[:limit]

    return orders


def get_last_order() -> Optional[Dict]:
    """Get the most recent order"""
    orders = get_order_history(limit=1)
    return orders[0] if orders else None


# ------------------- Shopping Assistant Agent -------------------
class ShoppingAssistantAgent(Agent):
    def __init__(self, *, tts=None):
        system_prompt = """You are a friendly and helpful voice shopping assistant. You help users browse products and place orders.

Key capabilities:
- Browse and filter products by category, price, color, etc.
- Search products by name or description
- Help users find what they're looking for
- Create orders when users want to buy something
- Check order history

Always be conversational and helpful. When showing products, mention key details like name, price, color, and notable features. When creating orders, confirm the details before proceeding.

When users ask for specific products like "coffee mugs", search across product names, descriptions, and categories to find relevant items.

Follow the ACP-inspired pattern: use the provided tools for all commerce operations."""
        super().__init__(instructions=system_prompt, tts=tts)

    @function_tool()
    async def browse_products(self, context: RunContext, payload: Optional[Dict] = None) -> str:
        """Browse products with optional filters and search (robust payload parsing)"""
        payload = payload or {}

        # Extract fields safely
        category = payload.get("category")
        max_price = payload.get("max_price")
        color = payload.get("color")
        search = payload.get("search") or payload.get("q")

        filters = {}

        if category:
            filters["category"] = category

        if max_price is not None:
            try:
                filters["max_price"] = int(max_price)
            except:
                pass

        if color:
            filters["color"] = color.lower()

        products = list_products(filters, search)

        if not products:
            msg = f"No products found matching '{search}'." if search else "No products found."
            return json.dumps({"message": msg, "products": []})

        summaries = []
        for p in products:
            d = {
                "id": p["id"],
                "name": p["name"],
                "price": p["price"],
                "currency": p["currency"],
                "color": p.get("color"),
                "in_stock": p["in_stock"],
                "description": p["description"],
            }
            if "size" in p:
                d["size"] = p["size"]
            summaries.append(d)

        return json.dumps({
            "message": f"Found {len(products)} products.",
            "products": summaries
        })

    @function_tool()
    async def place_order(self, context: RunContext, payload: Optional[Dict] = None) -> str:
        """Place an order. Accepts:
           - payload={'product_id': 'hoodie-002', 'quantity': 2}
           - payload={'order_details': [{'product_id': 'hoodie-002', 'quantity': 2}, ...]}
           - payload={'items': [...]}
        Normalizes input and calls create_order().
        """
        payload = payload or {}

        # 1) Try list-style order_details / items
        items_payload = payload.get("order_details") or payload.get("items")
        line_items = []

        if items_payload and isinstance(items_payload, list):
            for it in items_payload:
                # accept forgiving keys
                pid = it.get("product_id") or it.get("id") or it.get("product")
                qty = it.get("quantity", it.get("qty", 1))
                try:
                    qty = int(qty)
                except:
                    qty = 1
                if not pid:
                    # skip malformed item entries
                    continue
                line_items.append({"product_id": pid, "quantity": qty})

        else:
            # 2) Try single-item payload
            pid = payload.get("product_id") or payload.get("id") or payload.get("product")
            qty = payload.get("quantity", payload.get("qty", 1))
            try:
                qty = int(qty)
            except:
                qty = 1
            if pid:
                line_items.append({"product_id": pid, "quantity": qty})

        if not line_items:
            return json.dumps({
                "success": False,
                "message": "No valid product items found in payload. Provide 'product_id' or 'order_details' list."
            })

        # Validate products exist & are in stock before creating order (nice to fail early)
        bad = []
        for li in line_items:
            prod = next((p for p in PRODUCTS if p["id"] == li["product_id"]), None)
            if not prod:
                bad.append(f"{li['product_id']} (not found)")
            elif not prod.get("in_stock", False):
                bad.append(f"{prod['name']} (out of stock)")

        if bad:
            return json.dumps({
                "success": False,
                "message": "Cannot place order due to invalid items: " + "; ".join(bad)
            })

        # Create the order using authoritative prices from PRODUCTS
        try:
            order = create_order([{"product_id": li["product_id"], "quantity": li["quantity"]} for li in line_items])
        except Exception as e:
            return json.dumps({
                "success": False,
                "message": f"Failed to create order: {str(e)}"
            })

        # Build human-friendly summary
        items_desc = ", ".join([f"{it['quantity']} x {it['name']}" for it in order["items"]])
        return json.dumps({
            "success": True,
            "order_id": order["id"],
            "message": f"Order placed: {items_desc}. Total {order['total']} {order['currency']}.",
            "order_details": {
                "total": order["total"],
                "currency": order["currency"],
                "status": order["status"]
            }
        })


    @function_tool()
    async def get_last_order_info(self, context: RunContext, payload: Optional[Dict] = None) -> str:
        """Return the most recent order (no required params)"""
        order = get_last_order()

        if not order:
            return json.dumps({"message": "No previous orders found."})

        items_desc = ", ".join(
            f"{i['quantity']} x {i['name']}" for i in order["items"]
        )

        return json.dumps({
            "order_id": order["id"],
            "message": (
                f"Your last order was on {order['created_at'][:10]} "
                f"for {order['total']} INR. Items: {items_desc}."
            ),
            "total": order["total"],
            "currency": order["currency"],
            "status": order["status"]
        })

    @function_tool()
    async def get_order_history(self, context: RunContext, payload: Optional[Dict] = None) -> str:
        """Return order history with optional limit"""
        payload = payload or {}

        limit = payload.get("limit", 5)
        try:
            limit = int(limit)
        except:
            limit = 5

        orders = get_order_history(limit)

        if not orders:
            return json.dumps({"message": "No order history available."})

        history = []
        total_spent = 0

        for order in orders:
            items = ", ".join([f"{i['quantity']}x {i['name']}" for i in order["items"]])
            history.append({
                "date": order["created_at"][:10],
                "total": order["total"],
                "items": items
            })
            total_spent += order["total"]

        return json.dumps({
            "message": f"Found {len(orders)} past orders.",
            "orders": history,
            "total_orders": len(orders),
            "total_spent": total_spent
        })

    async def on_enter(self) -> None:
        """Welcome message when agent enters"""
        welcome_msg = "Hello! I'm your shopping assistant. I can help you browse products, check prices, and place orders. What would you like to do today?"
        await self.speak_text(welcome_msg)

    async def speak_text(self, text: str):
        """Helper to speak text with TTS"""
        if not text.strip():
            return

        max_chars = 700
        chunks = [text[i:i + max_chars] for i in range(0, len(text), max_chars)]

        for chunk in chunks:
            try:
                if hasattr(self.session.tts, "stream_text"):
                    async for _ in self.session.tts.stream_text(chunk):
                        pass
                elif hasattr(self.session.tts, "synthesize"):
                    result = self.session.tts.synthesize(chunk)
                    if asyncio.iscoroutine(result):
                        await result
            except Exception:
                logger.exception("TTS chunk failed")
                break


# ------------------- prewarm & entrypoint -------------------


def prewarm(proc: JobProcess):
    try:
        proc.userdata['vad'] = silero.VAD.load()
    except Exception:
        logger.exception('Failed to prewarm VAD')


async def entrypoint(ctx: JobContext):
    ctx.log_context_fields = {"room": ctx.room.name}

    # Initialize Murf TTS
    tts = murf.TTS(voice="en-US-matthew", style="Conversational")
    logger.info("Created Murf TTS instance for ShoppingAssistantAgent.")

    # Create agent session
    session = AgentSession(
        stt=deepgram.STT(model="nova-3"),
        llm=google.LLM(model="gemini-2.5-flash"),
        tts=tts,
        turn_detection=MultilingualModel(),
        vad=ctx.proc.userdata.get('vad'),
        preemptive_generation=True,
    )

    # Cleanup callback
    async def _close_tts():
        try:
            close_coro = getattr(tts, "close", None)
            if close_coro:
                if asyncio.iscoroutinefunction(close_coro):
                    await close_coro()
                else:
                    close_coro()
                logger.info("Closed Murf TTS instance cleanly on shutdown.")
        except Exception as e:
            logger.exception("Error closing Murf TTS: %s", e)

    ctx.add_shutdown_callback(_close_tts)

    # Start the shopping assistant
    await session.start(
        agent=ShoppingAssistantAgent(tts=tts),
        room=ctx.room,
        room_input_options=RoomInputOptions(
            noise_cancellation=noise_cancellation.BVC(),
        ),
    )
    await ctx.connect()


if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint, prewarm_fnc=prewarm))