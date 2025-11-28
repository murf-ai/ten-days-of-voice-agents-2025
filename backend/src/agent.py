# backend/src/agent.py
import logging
import os
import json
from datetime import datetime
from typing import List, Dict, Any, Optional

from dotenv import load_dotenv

from livekit.agents import (
    Agent,
    AgentSession,
    JobContext,
    JobProcess,
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

logger = logging.getLogger("agent_day7")
logger.setLevel(logging.INFO)

load_dotenv(".env.local")

# Paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHARED_DIR = os.path.join(BASE_DIR, "shared-data")
os.makedirs(SHARED_DIR, exist_ok=True)
CATALOG_PATH = os.path.join(SHARED_DIR, "catalog.json")
ORDERS_PATH = os.path.join(SHARED_DIR, "orders.json")

# --------- Catalog loader --------- #
def _load_catalog() -> List[Dict[str, Any]]:
    if not os.path.exists(CATALOG_PATH):
        raise FileNotFoundError(f"Catalog missing at {CATALOG_PATH}. Create a catalog.json in shared-data.")
    with open(CATALOG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

CATALOG = _load_catalog()
CATALOG_BY_ID = {item["id"]: item for item in CATALOG}
CATALOG_INDEX = {item["name"].lower(): item for item in CATALOG}

# Simple recipes mapping (dish -> list of catalog IDs)
RECIPES = {
    "peanut butter sandwich": ["bread_whole", "peanut_butter"],
    "pasta for two": ["pasta_500g", "pasta_sauce", "butter"],
    "sandwich": ["bread_whole", "butter", "jam"],
}

# --------- Orders persistence helpers --------- #
def _ensure_orders_file():
    if not os.path.exists(ORDERS_PATH):
        with open(ORDERS_PATH, "w", encoding="utf-8") as f:
            json.dump([], f, indent=2)

def _append_order(order: Dict[str, Any]):
    _ensure_orders_file()
    # load existing, append, write back
    with open(ORDERS_PATH, "r+", encoding="utf-8") as f:
        try:
            data = json.load(f)
        except Exception:
            data = []
        data.append(order)
        f.seek(0)
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.truncate()

# ---------- Tools (exposed to model) ---------- #

@function_tool
async def list_catalog(ctx: RunContext) -> List[Dict[str, Any]]:
    """Return a short list of catalog items for the model."""
    return [{"id": c["id"], "name": c["name"], "price": c["price"], "units": c.get("units")} for c in CATALOG]

@function_tool
async def add_item(ctx: RunContext, item_id: str, qty: int = 1) -> str:
    """Add item by id into session cart."""
    session = ctx.session
    cart = session.userdata.setdefault("cart", {})
    if item_id not in CATALOG_BY_ID:
        return f"Item id '{item_id}' not found in catalog."
    entry = cart.get(item_id, {"qty": 0})
    entry["qty"] = entry.get("qty", 0) + max(1, int(qty))
    cart[item_id] = entry
    session.userdata["cart"] = cart
    item = CATALOG_BY_ID[item_id]
    return f"Added {entry['qty']} × {item['name']} to your cart."

@function_tool
async def remove_item(ctx: RunContext, item_id: str) -> str:
    session = ctx.session
    cart = session.userdata.setdefault("cart", {})
    if item_id in cart:
        del cart[item_id]
        session.userdata["cart"] = cart
        return f"Removed {item_id} from your cart."
    return f"Item {item_id} not in your cart."

@function_tool
async def update_qty(ctx: RunContext, item_id: str, qty: int) -> str:
    session = ctx.session
    cart = session.userdata.setdefault("cart", {})
    if item_id not in CATALOG_BY_ID:
        return f"Unknown item id {item_id}."
    if qty <= 0:
        if item_id in cart:
            del cart[item_id]
        session.userdata["cart"] = cart
        return f"Removed {item_id} from the cart."
    cart[item_id] = {"qty": qty}
    session.userdata["cart"] = cart
    return f"Updated quantity: {qty} × {CATALOG_BY_ID[item_id]['name']}."

@function_tool
async def show_cart(ctx: RunContext) -> Dict[str, Any]:
    session = ctx.session
    cart = session.userdata.get("cart", {})
    items = []
    total = 0.0
    for item_id, info in cart.items():
        item = CATALOG_BY_ID.get(item_id)
        if not item:
            continue
        qty = info.get("qty", 1)
        price = item.get("price", 0)
        subtotal = price * qty
        items.append({"id": item_id, "name": item["name"], "qty": qty, "price": price, "subtotal": subtotal})
        total += subtotal
    return {"items": items, "total": round(total, 2)}

@function_tool
async def add_recipe_items(ctx: RunContext, dish_name: str, servings: int = 1) -> str:
    key = dish_name.strip().lower()
    if key not in RECIPES:
        return f"Don't have a recipe for '{dish_name}'. Try 'peanut butter sandwich' or 'pasta for two'."
    session = ctx.session
    cart = session.userdata.setdefault("cart", {})
    added = []
    for item_id in RECIPES[key]:
        base_qty = 1
        qty = max(1, int(servings * base_qty))
        entry = cart.get(item_id, {"qty": 0})
        entry["qty"] = entry.get("qty", 0) + qty
        cart[item_id] = entry
        added.append(CATALOG_BY_ID[item_id]["name"])
    session.userdata["cart"] = cart
    return f"Added {', '.join(added)} to your cart for '{dish_name}'."

@function_tool
async def place_order(ctx: RunContext, customer_name: Optional[str] = "Guest", address: Optional[str] = "") -> Dict[str, Any]:
    session = ctx.session
    cart = session.userdata.get("cart", {})
    if not cart:
        return {"error": "cart_empty", "message": "Your cart is empty."}
    order_items = []
    total = 0.0
    for item_id, info in cart.items():
        item = CATALOG_BY_ID.get(item_id)
        if not item:
            continue
        qty = info.get("qty", 1)
        subtotal = item["price"] * qty
        order_items.append({"id": item_id, "name": item["name"], "qty": qty, "unit_price": item["price"], "subtotal": subtotal})
        total += subtotal
    order = {
        "order_id": f"ORD-{int(datetime.utcnow().timestamp())}",
        "customer_name": customer_name,
        "address": address,
        "items": order_items,
        "total": round(total, 2),
        "timestamp": datetime.utcnow().isoformat(),
        "status": "placed"
    }
    _append_order(order)
    # clear cart
    session.userdata["cart"] = {}
    return {"success": True, "order": order}

# ---------- Agent class and behavior ---------- #

# Murf Falcon TTS voice (change IDs if your Murf voice names differ)
TTS_MATTHEW = murf.TTS(
    voice="en-US-matthew",
    style="Conversation",
    tokenizer=tokenize.basic.SentenceTokenizer(min_sentence_len=2),
    text_pacing=True,
)
TTS_ROUTER = TTS_MATTHEW

class ShoppingAgent(Agent):
    def __init__(self, **kwargs):
        instructions = f"""
You are a friendly shopping assistant for a demo grocery store. Use the provided tools:
list_catalog, add_item, remove_item, update_qty, show_cart, add_recipe_items, place_order.

Available sample recipes:
{json.dumps(list(RECIPES.keys()), indent=2)}

When the user asks for items or recipes, call the appropriate tools.
Confirm any cart changes verbally and ask follow-ups if needed (size/quantity/address).
When user says "place my order" or "that's all", call place_order and confirm the order summary.
"""
        super().__init__(instructions=instructions, tts=TTS_MATTHEW, **kwargs)

    async def on_enter(self) -> None:
        # Greeting
        await self.session.generate_reply(
            instructions=(
                "Greet the user warmly: 'Hi! I'm your grocery assistant. I can help you add items, "
                "add ingredients for a recipe (for example: peanut butter sandwich), show your cart, "
                "and place your order. What would you like to do today?'"
            )
        )

# ---------- Prewarm VAD ---------- #
def prewarm(proc: JobProcess):
    proc.userdata["vad"] = silero.VAD.load()

# ---------- Entrypoint ---------- #
async def entrypoint(ctx: JobContext):
    ctx.log_context_fields = {"room": ctx.room.name}
    session = AgentSession(
        stt=deepgram.STT(model="nova-3"),
        llm=google.LLM(model="gemini-2.5-flash"),
        # leave session-level tts None so agent's tts is used
        tts=None,
        turn_detection=MultilingualModel(),
        vad=ctx.proc.userdata["vad"],
        preemptive_generation=True,
        tools=[list_catalog, add_item, remove_item, update_qty, show_cart, add_recipe_items, place_order],
    )

    # initialize userdata
    session.userdata = {"cart": {}}

    usage_collector = metrics.UsageCollector()
    @session.on("metrics_collected")
    def _on_metrics_collected(ev):
        metrics.log_metrics(ev.metrics)
        usage_collector.collect(ev.metrics)

    async def log_usage():
        logger.info("Usage summary: %s", usage_collector.get_summary())

    ctx.add_shutdown_callback(log_usage)

    await session.start(agent=ShoppingAgent(), room=ctx.room, room_input_options=RoomInputOptions(noise_cancellation=noise_cancellation.BVC()))
    await ctx.connect()

if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint, prewarm_fnc=prewarm))
