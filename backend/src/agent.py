# Full Shopping Voice Agent (ShoppingAgent) with robust TTS chunking + fallback
# Replace your existing agent_sdr.py with this file or save as agent_shopping_full.py
# Notes:
# - This uses murf.TTS as before. The speak_text(...) helper attempts to stream with
#   `tts.stream_text(...)` and falls back to other methods; if your Murf plugin exposes
#   a differently-named method, adjust the calls in speak_text accordingly.
# - The agent reads only a short catalog preview on enter and uses speak_text to avoid
#   sending very long blocks to TTS in one shot.

import logging
import os
import json
import datetime
import inspect
import uuid
import asyncio
import re
from pathlib import Path
from typing import Optional, List, Dict, Any, Iterable

from dotenv import load_dotenv
from livekit import rtc
from livekit.agents import (
    Agent,
    AgentServer,
    AgentSession,
    JobContext,
    JobProcess,
    RunContext,
    MetricsCollectedEvent,
    RoomInputOptions,
    WorkerOptions,
    inference,
    cli,
    metrics,
    tokenize,
    room_io,
    function_tool,
)
from livekit.plugins import murf, silero, google, deepgram, noise_cancellation
from livekit.plugins.turn_detector.multilingual import MultilingualModel

logger = logging.getLogger("agent")
load_dotenv(".env.local")

# ---------- Paths & Data ---------- #

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(os.path.dirname(BASE_DIR), "shared-data")
os.makedirs(DATA_DIR, exist_ok=True)

CATALOG_PATH = os.path.join(DATA_DIR, "catalog.json")
ORDERS_PATH = os.path.join(DATA_DIR, "orders.json")

# Seed catalog (same sample as earlier)
SAMPLE_CATALOG: List[Dict[str, Any]] = [
    {"id": "milk-1l", "name": "Milk 1L", "category": "Groceries", "price": 60, "brand": "FreshDairy", "unit": "1L", "tags": ["dairy"]},
    {"id": "bread-white", "name": "White Bread (loaf)", "category": "Groceries", "price": 35, "brand": "BakeHouse", "unit": "loaf", "tags": ["breads"]},
    {"id": "bread-wholewheat", "name": "Whole Wheat Bread (loaf)", "category": "Groceries", "price": 45, "brand": "BakeHouse", "unit": "loaf", "tags": ["breads", "whole-wheat"]},
    {"id": "peanut-butter-200g", "name": "Peanut Butter 200g", "category": "Groceries", "price": 150, "brand": "Nutty", "unit": "200g", "tags": ["spread", "vegan"]},
    {"id": "pasta-500g", "name": "Pasta 500g", "category": "Groceries", "price": 90, "brand": "PastaCo", "unit": "500g", "tags": ["instant", "vegan"]},
    {"id": "pasta-sauce-400g", "name": "Tomato Pasta Sauce 400g", "category": "Groceries", "price": 120, "brand": "Saucy", "unit": "400g", "tags": ["sauce", "vegan"]},
    {"id": "eggs-6", "name": "Eggs (6 pcs)", "category": "Groceries", "price": 60, "brand": "FarmFresh", "unit": "6pcs", "tags": ["eggs", "protein"]},
    {"id": "apple-kg", "name": "Apples (1 kg)", "category": "Groceries", "price": 180, "brand": "Orchard", "unit": "1kg", "tags": ["fruits", "vegan"]},
    {"id": "chips-plain", "name": "Potato Chips 100g", "category": "Snacks", "price": 40, "brand": "CrispIt", "unit": "100g", "tags": ["snack", "veg"]},
    {"id": "sandwich-chicken", "name": "Chicken Sandwich (ready)", "category": "Prepared Food", "price": 150, "brand": "QuickBite", "unit": "each", "tags": ["ready", "non-veg"]},
    {"id": "samosa-2", "name": "Samosa (2 pcs)", "category": "Prepared Food", "price": 40, "brand": "StreetSnacks", "unit": "2pcs", "tags": ["veg", "ready"]},
    {"id": "butter-100g", "name": "Salted Butter 100g", "category": "Groceries", "price": 95, "brand": "Creamy", "unit": "100g", "tags": ["dairy"]},
    {"id": "rice-5kg", "name": "Basmati Rice 5kg", "category": "Groceries", "price": 420, "brand": "RiceKing", "unit": "5kg", "tags": ["staples"]},
    {"id": "sauce-chili", "name": "Chili Sauce 200g", "category": "Groceries", "price": 85, "brand": "HotZone", "unit": "200g", "tags": ["condiment", "vegan"]},
    {"id": "banana-kg", "name": "Bananas (1 kg)", "category": "Groceries", "price": 60, "brand": "Orchard", "unit": "1kg", "tags": ["fruits", "vegan"]},
]

# recipes: dish -> list of catalog IDs
RECIPES: Dict[str, List[str]] = {
    "peanut butter sandwich": ["bread-wholewheat", "peanut-butter-200g"],
    "pb sandwich": ["bread-wholewheat", "peanut-butter-200g"],
    "pasta for two": ["pasta-500g", "pasta-sauce-400g"],
    "eggs and toast": ["eggs-6", "bread-white"],
    "banana smoothie": ["banana-kg", "milk-1l"],
}

ORDER_STATUSES = ["received", "confirmed", "being_prepared", "out_for_delivery", "delivered"]

# Ensure files exist
def ensure_files():
    if not os.path.exists(CATALOG_PATH):
        with open(CATALOG_PATH, "w", encoding="utf-8") as f:
            json.dump(SAMPLE_CATALOG, f, indent=2, ensure_ascii=False)
    if not os.path.exists(ORDERS_PATH):
        with open(ORDERS_PATH, "w", encoding="utf-8") as f:
            json.dump([], f, indent=2)

ensure_files()

# load/save helpers

def load_catalog() -> List[Dict[str, Any]]:
    with open(CATALOG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def load_orders() -> List[Dict[str, Any]]:
    with open(ORDERS_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save_orders(orders: List[Dict[str, Any]]) -> None:
    with open(ORDERS_PATH, "w", encoding="utf-8") as f:
        json.dump(orders, f, indent=2, ensure_ascii=False)

# ---------- Robust TTS helpers (chunking + retries + fallback) ---------- #

_MAX_TTS_CHARS = 700  # conservative chunk size; lower if you still see failures

async def _split_into_chunks(text: str, max_chars: int = _MAX_TTS_CHARS) -> List[str]:
    text = (text or "").strip()
    if not text:
        return []
    # split on sentence boundaries first
    sentences = re.split(r'(?<=[.!?])\s+', text)
    chunks: List[str] = []
    current = ""
    for s in sentences:
        s = s.strip()
        if not s:
            continue
        if len(current) + len(s) + 1 <= max_chars:
            current = (current + " " + s).strip() if current else s
        else:
            if current:
                chunks.append(current)
            if len(s) <= max_chars:
                current = s
            else:
                # break long sentence into words
                words = s.split()
                piece = ""
                for w in words:
                    if len(piece) + len(w) + 1 <= max_chars:
                        piece = (piece + " " + w).strip() if piece else w
                    else:
                        if piece:
                            chunks.append(piece)
                        piece = w
                if piece:
                    current = piece
                else:
                    current = ""
    if current:
        chunks.append(current)
    return chunks


async def speak_text(session: AgentSession, tts, text: str, retries: int = 2):
    """
    Speak text by splitting into chunks and streaming each chunk via tts.
    - Tries `tts.stream_text(chunk)` if available (async iterator).
    - Falls back to calling `tts.synthesize(chunk)` if present.
    - If Murf fails repeatedly, tries silero as a fallback (if configured).
    NOTE: If your TTS plugin exposes a different interface, adapt the calls inside.
    """
    if not text or not text.strip():
        return

    chunks = await _split_into_chunks(text, _MAX_TTS_CHARS)
    if not chunks:
        return

    for chunk in chunks:
        success = False
        last_exc = None
        for attempt in range(retries + 1):
            try:
                # Preferred: async iterator style (streaming)
                if hasattr(tts, "stream_text"):
                    async for _frame in tts.stream_text(chunk):
                        # consuming frames is sufficient; agent runtime will route to audio output
                        pass
                    success = True
                    break
                # Alternative: `synthesize` may return bytes or an async generator
                if hasattr(tts, "synthesize"):
                    synth = tts.synthesize(chunk)
                    if inspect.isawaitable(synth):
                        # some implementations return a coroutine
                        await synth
                    else:
                        # maybe it returned an iterable of frames
                        for _ in synth:
                            pass
                    success = True
                    break
                # Last resort: try calling generate/tts-like method
                if hasattr(tts, "generate_audio"):
                    gen = tts.generate_audio(chunk)
                    if inspect.isawaitable(gen):
                        await gen
                    else:
                        for _ in gen:
                            pass
                    success = True
                    break
                # If none of these exist, raise for visibility
                raise RuntimeError("No known streaming method on TTS plugin (expected stream_text/synthesize/generate_audio)")
            except Exception as e:
                last_exc = e
                logger.warning("TTS attempt %d failed for chunk (len=%d): %s", attempt + 1, len(chunk), repr(e))
                await asyncio.sleep(0.6 * (attempt + 1))
        if not success:
            # fallback to silero if available
            try:
                if 'silero' in globals() and hasattr(silero, 'TTS'):
                    sil = silero.TTS()
                    if hasattr(sil, 'stream_text'):
                        async for _ in sil.stream_text(chunk):
                            pass
                    else:
                        maybe = sil.synthesize(chunk)
                        if inspect.isawaitable(maybe):
                            await maybe
                        else:
                            for _ in maybe:
                                pass
                    logger.info("Silero fallback succeeded for chunk.")
                    success = True
                else:
                    logger.error("No Silero available as fallback.")
            except Exception as e2:
                logger.exception("Fallback Silero TTS failed: %s", e2)

        if not success:
            # final fallback: speak a short apology so the agent doesn't hang
            try:
                short = "Sorry, I'm having trouble speaking right now. Please check the app for text output."
                if hasattr(tts, "stream_text"):
                    async for _ in tts.stream_text(short):
                        pass
                elif hasattr(tts, "synthesize"):
                    maybe2 = tts.synthesize(short)
                    if inspect.isawaitable(maybe2):
                        await maybe2
            except Exception:
                logger.exception("Final short fallback also failed for chunk.")
            # continue to next chunk regardless

# ---------- Cart helpers ---------- #

def _ensure_cart(session: AgentSession) -> Dict[str, Any]:
    ud = getattr(session, "userdata", None)
    if ud is None:
        session.userdata = {}
        ud = session.userdata
    cart = ud.get("cart")
    if not isinstance(cart, dict):
        cart = {}
        ud["cart"] = cart
    return cart


def _find_item(catalog: List[Dict[str, Any]], query: str) -> Optional[Dict[str, Any]]:
    if not query:
        return None
    q = query.strip().lower()
    for it in catalog:
        if it.get("id", "").lower() == q:
            return it
    for it in catalog:
        if q in it.get("name", "").lower():
            return it
    for it in catalog:
        if q in (it.get("brand") or "").lower():
            return it
    return None


def _cart_total(cart: Dict[str, Any]) -> float:
    total = 0.0
    for entry in cart.values():
        total += float(entry.get("unit_price", 0)) * int(entry.get("qty", 0))
    return total


def _summarize_cart(cart: Dict[str, Any]) -> Dict[str, Any]:
    items = list(cart.values())
    total = _cart_total(cart)
    return {"items": items, "total": total}


def _get_order(orders: List[Dict[str, Any]], order_id: str) -> Optional[Dict[str, Any]]:
    for o in orders:
        if o.get("id") == order_id:
            return o
    return None


def _advance_status(order: Dict[str, Any]) -> None:
    status = order.get("status", ORDER_STATUSES[0])
    try:
        idx = ORDER_STATUSES.index(status)
    except ValueError:
        idx = 0
    if idx < len(ORDER_STATUSES) - 1:
        order["status"] = ORDER_STATUSES[idx + 1]

# ---------- Shopping Agent ---------- #

class ShoppingAgent(Agent):
    def __init__(self, *, tts=None, extra_instructions: str = "", **kwargs):
        base_instructions = f"""
You are a friendly food and grocery ordering assistant named Grocy Cart.
Help users list catalog items, manage a cart, assemble simple recipes as ingredients, and place orders.
Keep responses short and confirm each cart change. Ask clarifying questions only when necessary.
"""
        super().__init__(instructions=base_instructions, tts=tts, **kwargs)

    @function_tool()
    async def list_catalog(self, context: RunContext) -> str:
        catalog = load_catalog()
        brief = [
            {"id": it.get("id"), "name": it.get("name"), "category": it.get("category"), "price": it.get("price"), "unit": it.get("unit")} for it in catalog
        ]
        return json.dumps({"count": len(brief), "items": brief})

    @function_tool()
    async def add_item(self, context: RunContext, item_query: str, qty: Optional[int] = 1) -> str:
        session = context.session
        catalog = load_catalog()
        item = _find_item(catalog, item_query)
        if not item:
            return json.dumps({"ok": False, "message": f"I couldn't find '{item_query}' in the catalog."})
        qty = max(int(qty or 1), 1)
        cart = _ensure_cart(session)
        entry = cart.get(item["id"])
        if entry:
            entry["qty"] = int(entry["qty"]) + qty
        else:
            cart[item["id"]] = {"id": item["id"], "name": item["name"], "unit_price": item["price"], "qty": qty, "unit": item.get("unit"), "tags": item.get("tags", [])}
        summary = _summarize_cart(cart)
        return json.dumps({"ok": True, "message": f"Added {qty} × {item['name']} to your cart.", "cart": summary})

    @function_tool()
    async def remove_item(self, context: RunContext, item_query: str) -> str:
        session = context.session
        catalog = load_catalog()
        cart = _ensure_cart(session)
        item = _find_item(catalog, item_query)
        if item and item["id"] in cart:
            removed_name = cart[item["id"]]["name"]
            del cart[item["id"]]
            summary = _summarize_cart(cart)
            return json.dumps({"ok": True, "message": f"Removed {removed_name} from your cart.", "cart": summary})
        if item_query in cart:
            removed_name = cart[item_query]["name"]
            del cart[item_query]
            summary = _summarize_cart(cart)
            return json.dumps({"ok": True, "message": f"Removed {removed_name} from your cart.", "cart": summary})
        return json.dumps({"ok": False, "message": "That item is not currently in your cart."})

    @function_tool()
    async def update_item(self, context: RunContext, item_query: str, qty: int) -> str:
        session = context.session
        catalog = load_catalog()
        cart = _ensure_cart(session)
        item = _find_item(catalog, item_query)
        if not item:
            return json.dumps({"ok": False, "message": f"I couldn't find '{item_query}' in the catalog."})
        if item["id"] not in cart:
            return json.dumps({"ok": False, "message": f"{item['name']} is not in your cart yet."})
        qty = max(int(qty), 0)
        if qty == 0:
            del cart[item["id"]]
            summary = _summarize_cart(cart)
            return json.dumps({"ok": True, "message": f"Removed {item['name']} from your cart.", "cart": summary})
        cart[item["id"]]["qty"] = qty
        summary = _summarize_cart(cart)
        return json.dumps({"ok": True, "message": f"Updated {item['name']} to quantity {qty}.", "cart": summary})

    @function_tool()
    async def show_cart(self, context: RunContext) -> str:
        session = context.session
        cart = _ensure_cart(session)
        summary = _summarize_cart(cart)
        empty = len(summary["items"]) == 0
        return json.dumps({"ok": True, "empty": empty, "cart": summary, "message": "Your cart is empty." if empty else "Here is your current cart."})

    @function_tool()
    async def add_ingredients_for(self, context: RunContext, dish: str) -> str:
        session = context.session
        catalog = load_catalog()
        key = dish.strip().lower()
        if key not in RECIPES:
            return json.dumps({"ok": False, "message": f"I don't have a recipe for '{dish}'. Try: {', '.join(RECIPES.keys())}"})
        cart = _ensure_cart(session)
        added_names: List[str] = []
        for item_id in RECIPES[key]:
            item = _find_item(catalog, item_id)
            if not item:
                continue
            existing = cart.get(item["id"])
            if existing:
                existing["qty"] = existing["qty"] + 1
            else:
                cart[item["id"]] = {"id": item["id"], "name": item["name"], "unit_price": item["price"], "qty": 1, "unit": item.get("unit"), "tags": item.get("tags", [])}
            added_names.append(item["name"])
        summary = _summarize_cart(cart)
        return json.dumps({"ok": True, "message": f"I've added ingredients for {dish}: " + ", ".join(added_names), "cart": summary})

    @function_tool()
    async def place_order(self, context: RunContext, customer_name: str, address: str = "", note: str = "") -> str:
        session = context.session
        cart = _ensure_cart(session)
        if not cart:
            return json.dumps({"ok": False, "message": "Your cart is empty, so I can't place an order."})
        orders = load_orders()
        cart_summary = _summarize_cart(cart)
        order_id = f"ORD-{uuid.uuid4().hex[:10].upper()}"
        now = datetime.datetime.utcnow().isoformat() + "Z"
        order = {"id": order_id, "timestamp": now, "customer": {"name": customer_name.strip() or "Guest", "address": address.strip(), "note": note.strip()}, "items": cart_summary["items"], "total": cart_summary["total"], "status": ORDER_STATUSES[0], "type": "grocery"}
        orders.append(order)
        save_orders(orders)
        session.userdata["cart"] = {}
        return json.dumps({"ok": True, "message": f"Your order has been placed. Order ID is {order_id}.", "order": order})

    @function_tool()
    async def order_status(self, context: RunContext, order_id: str) -> str:
        orders = load_orders()
        order = _get_order(orders, order_id)
        if not order:
            return json.dumps({"ok": False, "message": f"I couldn't find an order with ID {order_id}."})
        return json.dumps({"ok": True, "status": order.get("status"), "order": {"id": order.get("id"), "total": order.get("total"), "timestamp": order.get("timestamp"), "status": order.get("status")}})

    @function_tool()
    async def list_orders(self, context: RunContext) -> str:
        orders = load_orders()
        brief = [{"id": o.get("id"), "timestamp": o.get("timestamp"), "total": o.get("total"), "status": o.get("status"), "type": o.get("type", "grocery")} for o in orders]
        return json.dumps({"count": len(brief), "orders": brief})

    @function_tool()
    async def advance_order(self, context: RunContext, order_id: str) -> str:
        orders = load_orders()
        order = _get_order(orders, order_id)
        if not order:
            return json.dumps({"ok": False, "message": f"Order {order_id} not found."})
        old_status = order.get("status")
        if old_status == ORDER_STATUSES[-1]:
            return json.dumps({"ok": False, "message": "This order is already delivered."})
        _advance_status(order)
        save_orders(orders)
        return json.dumps({"ok": True, "message": f"Order {order_id} moved from {old_status} to {order['status']}.", "status": order["status"]})

    async def on_enter(self) -> None:
        # Speak a short greeting and a catalog preview using speak_text to avoid huge single-TTS payloads
        greeting = "Hello — I'm Grocy Cart, your grocery assistant. I can help you order groceries and quick snacks."
        await speak_text(self.session, self.session.tts, greeting)

        # read a short preview of catalog (top 6 items)
        catalog = load_catalog()
        preview = catalog[:6]
        lines = ["Here's a quick preview of top items:"]
        for it in preview:
            lines.append(f"{it['name']} — {it['price']} rupees ({it.get('unit','')})")
        lines.append("Would you like me to read more, or add something to your cart?")
        short_msg = " ".join(lines)
        await speak_text(self.session, self.session.tts, short_msg)

# ---------- prewarm & entrypoint ---------- #

def prewarm(proc: JobProcess):
    proc.userdata["vad"] = silero.VAD.load()


async def entrypoint(ctx: JobContext):
    ctx.log_context_fields = {"room": ctx.room.name}

    tts = murf.TTS(voice="en-US-matthew", style="Conversation", tokenizer=tokenize.basic.SentenceTokenizer(min_sentence_len=2), text_pacing=True)
    logger.info("Created Murf TTS instance for ShoppingAgent.")

    session = AgentSession(
        stt=deepgram.STT(model="nova-3"),
        llm=google.LLM(model="gemini-2.5-flash"),
        tts=tts,
        turn_detection=MultilingualModel(),
        vad=ctx.proc.userdata["vad"],
        preemptive_generation=True,
    )

    session.userdata = {}
    usage_collector = metrics.UsageCollector()

    @session.on("metrics_collected")
    def _on_metrics_collected(ev: MetricsCollectedEvent):
        metrics.log_metrics(ev.metrics)
        usage_collector.collect(ev.metrics)

    async def log_usage():
        summary = usage_collector.get_summary()
        logger.info(f"Usage: {summary}")

    ctx.add_shutdown_callback(log_usage)

    async def _close_tts():
        try:
            close_coro = getattr(tts, "close", None)
            if close_coro:
                if inspect.iscoroutinefunction(close_coro):
                    await close_coro()
                else:
                    close_coro()
                logger.info("Closed Murf TTS instance cleanly on shutdown.")
        except Exception as e:
            logger.exception("Error closing Murf TTS: %s", e)

    ctx.add_shutdown_callback(_close_tts)

    await session.start(
        agent=ShoppingAgent(tts=tts),
        room=ctx.room,
        room_input_options=RoomInputOptions(
            noise_cancellation=noise_cancellation.BVC(),
        ),
    )
    await ctx.connect()


if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint, prewarm_fnc=prewarm))
