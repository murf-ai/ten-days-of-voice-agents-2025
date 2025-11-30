

import json
import logging
import os
import asyncio
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Optional, Annotated

from dotenv import load_dotenv
from pydantic import Field
from livekit.agents import (
    Agent,
    AgentSession,
    JobContext,
    JobProcess,
    RoomInputOptions,
    WorkerOptions,
    cli,
    function_tool,
    RunContext,
)

from livekit.plugins import murf, silero, google, deepgram, noise_cancellation
from livekit.plugins.turn_detector.multilingual import MultilingualModel

# -------------------------
# Logging
# -------------------------
logger = logging.getLogger("voice_game_master")
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
logger.addHandler(handler)

load_dotenv(".env.local")

# -------------------------
# Simple Product Catalog (Dr Abhishek Shop)
# -------------------------
# A compact Indian-flavored catalog with attributes: id, name, price (INR), category, color, sizes
CATALOG = [
    {
        "id": "mug-001",
        "name": "Stoneware Chai Mug",
        "description": "Hand-glazed ceramic mug perfect for masala chai.",
        "price": 299,
        "currency": "INR",
        "category": "mug",
        "color": "blue",
        "sizes": [],
    },
    {
        "id": "tee-001",
        "name": "Dr Abhishek Tee (Cotton)",
        "description": "Comfort-fit cotton t-shirt with subtle logo.",
        "price": 799,
        "currency": "INR",
        "category": "tshirt",
        "color": "black",
        "sizes": ["S", "M", "L", "XL"],
    },
    {
        "id": "hoodie-001",
        "name": "Cozy Hoodie",
        "description": "Warm pullover hoodie, fleece-lined.",
        "price": 1499,
        "currency": "INR",
        "category": "hoodie",
        "color": "grey",
        "sizes": ["M", "L", "XL"],
    },
    {
        "id": "mug-002",
        "name": "Insulated Travel Mug",
        "description": "Keeps chai warm on your way to work.",
        "price": 599,
        "currency": "INR",
        "category": "mug",
        "color": "white",
        "sizes": [],
    },
    {
        "id": "hoodie-002",
        "name": "Black Zip Hoodie",
        "description": "Lightweight zip-up hoodie, black.",
        "price": 1299,
        "currency": "INR",
        "category": "hoodie",
        "color": "black",
        "sizes": ["S", "M", "L"],
    },
    # T-shirts (expanded)
    {
        "id": "tee-002",
        "name": "Casual Cotton Tee",
        "description": "Everyday cotton t-shirt, breathable and soft.",
        "price": 299,
        "currency": "INR",
        "category": "tshirt",
        "color": "white",
        "sizes": ["S", "M", "L", "XL"],
    },
    {
        "id": "tee-003",
        "name": "Graphic Tee",
        "description": "Printed graphic t-shirt with vibrant design.",
        "price": 499,
        "currency": "INR",
        "category": "tshirt",
        "color": "navy",
        "sizes": ["S", "M", "L", "XL"],
    },
    {
        "id": "tee-004",
        "name": "Premium Polo Tee",
        "description": "Polo-style t-shirt with premium stitching.",
        "price": 999,
        "currency": "INR",
        "category": "tshirt",
        "color": "maroon",
        "sizes": ["M", "L", "XL"],
    },
    {
        "id": "tee-005",
        "name": "Summer V-neck Tee",
        "description": "Lightweight V-neck tee for hot days.",
        "price": 350,
        "currency": "INR",
        "category": "tshirt",
        "color": "sky",
        "sizes": ["S", "M", "L"],
    },
    {
        "id": "tee-006",
        "name": "Henley Tee",
        "description": "Smart casual henley style t-shirt.",
        "price": 699,
        "currency": "INR",
        "category": "tshirt",
        "color": "olive",
        "sizes": ["M", "L", "XL"],
    },
    # Raincoats / Outerwear
    {
        "id": "rain-001",
        "name": "Light Raincoat",
        "description": "Waterproof light raincoat, packable.",
        "price": 1299,
        "currency": "INR",
        "category": "raincoat",
        "color": "yellow",
        "sizes": ["M", "L", "XL"],
    },
    {
        "id": "rain-002",
        "name": "Heavy Duty Raincoat",
        "description": "Heavy-duty rainproof coat for monsoon.",
        "price": 2499,
        "currency": "INR",
        "category": "raincoat",
        "color": "navy",
        "sizes": ["L", "XL"],
    },
    # Laptops
    {
        "id": "laptop-001",
        "name": "Generic Laptop (50k)",
        "description": "A reliable laptop suitable for everyday use.",
        "price": 50000,
        "currency": "INR",
        "category": "laptop",
        "color": "silver",
        "sizes": [],
    },
    {
        "id": "laptop-002",
        "name": "Dell Inspiron (Budget)",
        "description": "Compact Dell laptop for students and professionals.",
        "price": 27800,
        "currency": "INR",
        "category": "laptop",
        "color": "black",
        "sizes": [],
    },
    {
        "id": "laptop-003",
        "name": "Lenovo ThinkPad",
        "description": "Durable Lenovo laptop with strong performance.",
        "price": 60000,
        "currency": "INR",
        "category": "laptop",
        "color": "black",
        "sizes": [],
    },
    {
        "id": "laptop-004",
        "name": "HP Pavilion",
        "description": "High-performance HP laptop for creators.",
        "price": 100000,
        "currency": "INR",
        "category": "laptop",
        "color": "silver",
        "sizes": [],
    },
    # Storage
    {
        "id": "storage-001",
        "name": "External Hard Disk 1TB",
        "description": "Portable external hard disk for backups.",
        "price": 50000,
        "currency": "INR",
        "category": "storage",
        "color": "black",
        "sizes": [],
    },
    # Mobile phones (10k - 50k examples)
    {
        "id": "phone-001",
        "name": "Redmi Note (Entry)",
        "description": "Affordable Redmi smartphone with solid features.",
        "price": 12000,
        "currency": "INR",
        "category": "mobile",
        "color": "blue",
        "sizes": [],
    },
    {
        "id": "phone-002",
        "name": "Oppo A-Series",
        "description": "Stylish Oppo phone with good camera.",
        "price": 18000,
        "currency": "INR",
        "category": "mobile",
        "color": "green",
        "sizes": [],
    },
    {
        "id": "phone-003",
        "name": "Samsung M-Series",
        "description": "Mid-range Samsung phone for everyday use.",
        "price": 25000,
        "currency": "INR",
        "category": "mobile",
        "color": "black",
        "sizes": [],
    },
    {
        "id": "phone-004",
        "name": "iPhone (Standard)",
        "description": "Apple iPhone model example (price varies by config).",
        "price": 50000,
        "currency": "INR",
        "category": "mobile",
        "color": "white",
        "sizes": [],
    },
    {
        "id": "phone-005",
        "name": "Oppo Reno",
        "description": "Higher-end Oppo phone with premium features.",
        "price": 35000,
        "currency": "INR",
        "category": "mobile",
        "color": "black",
        "sizes": [],
    },
    {
        "id": "phone-006",
        "name": "Redmi Pro",
        "description": "Redmi higher-tier phone with improved camera and battery.",
        "price": 22000,
        "currency": "INR",
        "category": "mobile",
        "color": "grey",
        "sizes": [],
    },
]



ORDERS_FILE = "orders.json"

# ensure orders file exists
if not os.path.exists(ORDERS_FILE):
    with open(ORDERS_FILE, "w") as f:
        json.dump([], f)

# -------------------------
# Per-session Userdata (shopping-centric)
# -------------------------
@dataclass
class Userdata:
    player_name: Optional[str] = None  # retained name field (player -> customer)
    session_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    started_at: str = field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")
    cart: List[Dict] = field(default_factory=list)  # list of {product_id, quantity, attrs}
    orders: List[Dict] = field(default_factory=list)  # orders placed in this session
    history: List[Dict] = field(default_factory=list)  # conversational actions for trace

# -------------------------
# Merchant-layer helpers (ACP-inspired mini layer)
# -------------------------

def _load_all_orders() -> List[Dict]:
    try:
        with open(ORDERS_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return []


def _save_order(order: Dict):
    orders = _load_all_orders()
    orders.append(order)
    with open(ORDERS_FILE, "w") as f:
        json.dump(orders, f, indent=2)


def list_products(filters: Optional[Dict] = None) -> List[Dict]:
    """Naive filtering by category, max_price, color, size substring, or query words.

    Improvements:
    - Accepts category synonyms (e.g., 'phone', 'mobile', 'phones' -> 'mobile').
    - Supports a flexible max_price and min_price (if provided in filters).
    - Matches category by substring if exact match fails.
    """
    filters = filters or {}
    results = []
    query = filters.get("q")
    category = filters.get("category")
    max_price = filters.get("max_price") or filters.get("to") or filters.get("max")
    min_price = filters.get("min_price") or filters.get("from") or filters.get("min")
    color = filters.get("color")
    size = filters.get("size")

    # normalize category synonyms
    if category:
        cat = category.lower()
        if cat in ("phone", "phones", "mobile", "mobile phone", "mobiles"):
            category = "mobile"
        elif cat in ("tshirt", "t-shirts", "tees", "tee"):
            category = "tshirt"
        else:
            category = cat

    for p in CATALOG:
        ok = True
        # category matching: allow substring matches if direct equality fails
        if category:
            pcat = p.get("category", "").lower()
            if pcat != category and category not in pcat and pcat not in category:
                ok = False
        if max_price:
            try:
                if p.get("price", 0) > int(max_price):
                    ok = False
            except Exception:
                pass
        if min_price:
            try:
                if p.get("price", 0) < int(min_price):
                    ok = False
            except Exception:
                pass
        if color and p.get("color") and p.get("color") != color:
            ok = False
        if size and (not p.get("sizes") or size not in p.get("sizes")):
            ok = False
        if query:
            q = query.lower()
            # if query mentions 'phone' or 'mobile', accept mobile category too
            if "phone" in q or "mobile" in q:
                if p.get("category") != "mobile":
                    ok = False
            else:
                if q not in p.get("name", "").lower() and q not in p.get("description", "").lower():
                    ok = False
        if ok:
            results.append(p)
    return results


def find_product_by_ref(ref_text: str, candidates: Optional[List[Dict]] = None) -> Optional[Dict]:
    """Resolve references like 'second hoodie' or 'black hoodie' to a product dict.
    Heuristics improved:
    - Handle ordinals like 'first/second/third' within a filtered candidate list.
    - If ref mentions 'phone' or 'mobile' prefer mobile category products.
    - Match by id, color+category, name substring, or numeric index.
    """
    ref = (ref_text or "").lower().strip()
    cand = candidates if candidates is not None else CATALOG

    # prefer mobiles if user explicitly mentions phone/mobile
    wants_mobile = any(w in ref for w in ("phone", "phones", "mobile", "mobiles"))
    filtered = cand
    if wants_mobile:
        filtered = [p for p in cand if p.get("category") == "mobile"]
        if not filtered:
            filtered = cand

    # ordinal handling
    ordinals = {"first": 0, "second": 1, "third": 2, "fourth": 3}
    for word, idx in ordinals.items():
        if word in ref:
            if idx < len(filtered):
                return filtered[idx]

    # direct id match
    for p in cand:
        if p["id"].lower() == ref:
            return p

    # color + category matching
    for p in cand:
        if p.get("color") and p["color"] in ref and p.get("category") and p["category"] in ref:
            return p

    # name substring or keywords
    for p in filtered:
        name = p["name"].lower()
        if all(tok in name for tok in ref.split() if len(tok) > 2):
            return p
    for p in cand:
        for tok in ref.split():
            if len(tok) > 2 and tok in p["name"].lower():
                return p

    # numeric index like '2' -> second
    for token in ref.split():
        if token.isdigit():
            idx = int(token) - 1
            if 0 <= idx < len(filtered):
                return filtered[idx]

    # fallback: if user said 'second phone' but we couldn't match earlier, try overall cand ordinals
    for word, idx in ordinals.items():
        if word in ref and idx < len(cand):
            return cand[idx]

    return None


@function_tool
async def show_catalog(
    ctx: RunContext[Userdata],
    q: Annotated[Optional[str], Field(description="Search query (optional)", default=None)] = None,
    category: Annotated[Optional[str], Field(description="Category (optional)", default=None)] = None,
    max_price: Annotated[Optional[int], Field(description="Maximum price (optional)", default=None)] = None,
    color: Annotated[Optional[str], Field(description="Color (optional)", default=None)] = None,
) -> str:
    """Return a short spoken summary of matching products (name, price, id).
    Improvements:
    - Recognize category synonyms like 'phones' and 'tees'.
    - Return up to 8 items and explicitly call out mobiles if present.
    """
    userdata = ctx.userdata
    # try to normalize category input
    if category:
        cat = category.lower()
        if cat in ("phone", "phones", "mobile", "mobile phone", "mobiles"):
            category = "mobile"
        elif cat in ("tshirt", "t-shirts", "tees", "tee"):
            category = "tshirt"
        else:
            category = cat
    # If query mentions phones, prefer category mobile
    if not category and q:
        if any(w in q.lower() for w in ("phone", "phones", "mobile", "mobiles")):
            category = "mobile"
        if any(w in q.lower() for w in ("tee", "tshirt", "t-shirts", "tees")):
            category = "tshirt"

    filters = {"q": q, "category": category, "max_price": max_price, "color": color}
    prods = list_products({k: v for k, v in filters.items() if v is not None})
    if not prods:
        return "Sorry — I couldn't find any items that match. Would you like to try another search?"
    # Summarize top 8
    lines = [f"Here are the top {min(8, len(prods))} items I found at Dr Abhishek Shop:"]
    for idx, p in enumerate(prods[:8], start=1):
        size_info = f" (sizes: {', '.join(p['sizes'])})" if p.get('sizes') else ""
        lines.append(f"{idx}. {p['name']} — {p['price']} {p['currency']} (id: {p['id']}){size_info}")
    lines.append("You can say: 'I want the second item in size M' or 'add mug-001 to my cart, quantity 2'.")
    # If mobiles were in results, add a short phrasing hint
    if any(p.get('category') == 'mobile' for p in prods):
        lines.append("To buy a phone say: 'Add phone-002 to my cart' or 'I want the second phone, quantity 1'.")
    return "\n".join(lines)


def find_product_by_ref(ref_text: str, candidates: Optional[List[Dict]] = None) -> Optional[Dict]:
    """Resolve references like 'second hoodie' or 'black hoodie' to a product dict.
    Very simple heuristic: look for ordinal words, color or exact id/name matching.
    """
    ref = (ref_text or "").lower().strip()
    cand = candidates if candidates is not None else CATALOG

    # ordinal handling
    ordinals = {"first": 0, "second": 1, "third": 2}
    for word, idx in ordinals.items():
        if word in ref:
            if idx < len(cand):
                return cand[idx]

    # direct id match
    for p in cand:
        if p["id"].lower() == ref:
            return p

    # color + category matching
    for p in cand:
        if p.get("color") and p["color"] in ref and p.get("category") and p["category"] in ref:
            return p

    # name substring
    for p in cand:
        if p["name"].lower() in ref or any(w in p["name"].lower() for w in ref.split()):
            return p

    # fallback: if a number present, try to parse as '2nd of last list'
    for token in ref.split():
        if token.isdigit():
            idx = int(token) - 1
            if 0 <= idx < len(cand):
                return cand[idx]

    return None


def create_order_object(line_items: List[Dict], currency: str = "INR") -> Dict:
    """line_items: [{product_id, quantity, attrs}]
    Returns an order dict (id, items, total, currency, created_at)
    """
    items = []
    total = 0
    for li in line_items:
        pid = li.get("product_id")
        qty = int(li.get("quantity", 1))
        prod = next((p for p in CATALOG if p["id"] == pid), None)
        if not prod:
            raise ValueError(f"Product {pid} not found")
        line_total = prod["price"] * qty
        total += line_total
        items.append({
            "product_id": pid,
            "name": prod["name"],
            "unit_price": prod["price"],
            "quantity": qty,
            "line_total": line_total,
            "attrs": li.get("attrs", {}),
        })
    order = {
        "id": f"order-{str(uuid.uuid4())[:8]}",
        "items": items,
        "total": total,
        "currency": currency,
        "created_at": datetime.utcnow().isoformat() + "Z",
    }
    # persist
    _save_order(order)
    return order


def get_most_recent_order() -> Optional[Dict]:
    all_orders = _load_all_orders()
    if not all_orders:
        return None
    return all_orders[-1]

# -------------------------
# Agent Tools (function_tool) exposed to the LLM layer
# -------------------------

@function_tool
async def show_catalog(
    ctx: RunContext[Userdata],
    q: Annotated[Optional[str], Field(description="Search query (optional)", default=None)] = None,
    category: Annotated[Optional[str], Field(description="Category (optional)", default=None)] = None,
    max_price: Annotated[Optional[int], Field(description="Maximum price (optional)", default=None)] = None,
    color: Annotated[Optional[str], Field(description="Color (optional)", default=None)] = None,
) -> str:
    """Return a short spoken summary of matching products (name, price, id)."""
    userdata = ctx.userdata
    filters = {"q": q, "category": category, "max_price": max_price, "color": color}
    prods = list_products({k: v for k, v in filters.items() if v is not None})
    if not prods:
        return "Sorry — I couldn't find any items that match. Would you like to try another search?"
    # Summarize top 4
    lines = [f"Here are the top {min(4, len(prods))} items I found at Dr Abhishek Shop:"]
    for idx, p in enumerate(prods[:4], start=1):
        lines.append(f"{idx}. {p['name']} — {p['price']} {p['currency']} (id: {p['id']})")
    lines.append("You can say: 'I want the second item in size M' or 'add mug-001 to my cart, quantity 2'.")
    return "\n".join(lines)


@function_tool
async def add_to_cart(
    ctx: RunContext[Userdata],
    product_ref: Annotated[str, Field(description="Reference to product: id, name, or spoken ref")] ,
    quantity: Annotated[int, Field(description="Quantity", default=1)] = 1,
    size: Annotated[Optional[str], Field(description="Size (optional)", default=None)] = None,
) -> str:
    """Resolve a product and add to the session cart."""
    userdata = ctx.userdata
    # take recent catalog as candidates
    candidates = CATALOG
    prod = find_product_by_ref(product_ref, candidates)
    if not prod:
        return "I couldn't resolve which product you meant. Try using the item id or say 'show catalog' to hear options.'"
    userdata.cart.append({
        "product_id": prod["id"],
        "quantity": int(quantity),
        "attrs": {"size": size} if size else {},
    })
    userdata.history.append({
        "time": datetime.utcnow().isoformat() + "Z",
        "action": "add_to_cart",
        "product_id": prod["id"],
        "quantity": int(quantity),
    })
    return f"Added {quantity} x {prod['name']} to your cart. What would you like to do next?"


@function_tool
async def show_cart(
    ctx: RunContext[Userdata],
) -> str:
    userdata = ctx.userdata
    if not userdata.cart:
        return "Your cart is empty. You can say 'show catalog' to browse items.'"
    lines = ["Items in your cart:"]
    total = 0
    for li in userdata.cart:
        p = next((x for x in CATALOG if x["id"] == li["product_id"]), None)
        if not p:
            continue
        line_total = p["price"] * li.get("quantity", 1)
        total += line_total
        sz = li.get("attrs", {}).get("size")
        sz_text = f", size {sz}" if sz else ""
        lines.append(f"- {p['name']} x {li['quantity']}{sz_text}: {line_total} INR")
    lines.append(f"Cart total: {total} INR")
    lines.append("Say 'place my order' to checkout or 'clear cart' to empty the cart.")
    return "\n".join(lines)


@function_tool
async def clear_cart(
    ctx: RunContext[Userdata],
) -> str:
    userdata = ctx.userdata
    userdata.cart = []
    userdata.history.append({"time": datetime.utcnow().isoformat() + "Z", "action": "clear_cart"})
    return "Your cart has been cleared. What would you like to do next?"


@function_tool
async def place_order(
    ctx: RunContext[Userdata],
    confirm: Annotated[bool, Field(description="Confirm order placement", default=True)] = True,
) -> str:
    """Create order from session cart and persist. Returns order summary."""
    userdata = ctx.userdata
    if not userdata.cart:
        return "Your cart is empty — nothing to place. Would you like to browse items?"
    # Build line_items
    line_items = []
    for li in userdata.cart:
        line_items.append({
            "product_id": li["product_id"],
            "quantity": li.get("quantity", 1),
            "attrs": li.get("attrs", {}),
        })
    order = create_order_object(line_items)
    userdata.orders.append(order)
    userdata.history.append({"time": datetime.utcnow().isoformat() + "Z", "action": "place_order", "order_id": order["id"]})
    # clear cart after order
    userdata.cart = []
    return f"Order placed. Order ID {order['id']}. Total {order['total']} {order['currency']}. What would you like to do next?"


@function_tool
async def last_order(
    ctx: RunContext[Userdata],
) -> str:
    ord = get_most_recent_order()
    if not ord:
        return "You have no past orders yet."
    lines = [f"Most recent order: {ord['id']} — {ord['created_at']}"]
    for it in ord['items']:
        lines.append(f"- {it['name']} x {it['quantity']}: {it['line_total']} {ord['currency']}")
    lines.append(f"Total: {ord['total']} {ord['currency']}")
    return "\n".join(lines)

# -------------------------
# The Agent (Ramu Kaka)
# -------------------------
class GameMasterAgent(Agent):
    def __init__(self):
        # System instructions now describe the shopkeeper persona and commerce role
        instructions = """
        You are 'Ramu Kaka', the friendly shopkeeper and voice assistant for Dr Abhishek Shop.
        Universe: A small neighbourhood Indian shop selling mugs, hoodies and tees.
        Tone: Warm, helpful, slightly jocular; keep sentences short for TTS clarity.
        Role: Help the customer browse the catalog, add items to cart, place orders, and review recent orders.

        Rules:
            - Use the provided tools to show the catalog, add items to cart, show the cart, place orders, show last order and clear the cart.
            - Keep continuity using the per-session userdata. Mention cart contents if relevant.
            - Drive short voice-first turns suitable for spoken delivery.
            - When presenting options, include product id and price (e.g. 'mug-001 — 299 INR').
        """
        super().__init__(
            instructions=instructions,
            tools=[show_catalog, add_to_cart, show_cart, clear_cart, place_order, last_order],
        )

# -------------------------
# Entrypoint & Prewarm (keeps speech functionality untouched)
# -------------------------
def prewarm(proc: JobProcess):
    # load VAD model and stash on process userdata, try/catch like original file
    try:
        proc.userdata["vad"] = silero.VAD.load()
    except Exception:
        logger.warning("VAD prewarm failed; continuing without preloaded VAD.")


async def entrypoint(ctx: JobContext):
    ctx.log_context_fields = {"room": ctx.room.name}
    logger.info("\n" + "🛍️" * 6)
    logger.info("🚀 STARTING VOICE E-COMMERCE AGENT (Dr Abhishek Shop) — Ramu Kaka")

    userdata = Userdata()

    session = AgentSession(
        stt=deepgram.STT(model="nova-3"),
        llm=google.LLM(model="gemini-2.5-flash"),
        tts=murf.TTS(
            voice="en-US-marcus",
            style="Conversational",
            text_pacing=True,
        ),
        turn_detection=MultilingualModel(),
        vad=ctx.proc.userdata.get("vad"),
        userdata=userdata,
    )

    # Start the agent session with the GameMasterAgent (Ramu Kaka)
    await session.start(
        agent=GameMasterAgent(),
        room=ctx.room,
        room_input_options=RoomInputOptions(noise_cancellation=noise_cancellation.BVC()),
    )

    await ctx.connect()


if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint, prewarm_fnc=prewarm))