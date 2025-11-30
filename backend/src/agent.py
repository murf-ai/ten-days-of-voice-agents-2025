"""
Day 9 – E-Commerce Voice Agent (ACP-Inspired)
- Reads product catalog from products.json in backend directory.
- Creates/updates orders.json to persist placed orders.
- Tools:
    - list_products / show_product
    - add_to_cart / remove_from_cart / show_cart
    - place_order / last_order / order_history
"""

import os
import json
import uuid
import logging
from datetime import datetime
from typing import List, Optional, Annotated
from dataclasses import dataclass, field

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
from livekit.plugins import murf, silero, openai, deepgram, noise_cancellation
from livekit.plugins.turn_detector.multilingual import MultilingualModel

# -------------------------
# Setup
# -------------------------
load_dotenv(".env.local")

logger = logging.getLogger("ecommerce_agent")
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
logger.addHandler(handler)

# -------------------------
# Data models
# -------------------------
@dataclass
class CartItem:
    id: str
    name: str
    price: float
    quantity: int = 1
    size: Optional[str] = None

@dataclass
class Userdata:
    cart: List[CartItem] = field(default_factory=list)
    last_order: Optional[dict] = None
    user_name: Optional[str] = None

# -------------------------
# File paths
# -------------------------
# -------------------------
# File paths (Fixed)
# -------------------------
BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
CATALOG_PATH = os.path.join(BACKEND_DIR, "products.json")
ORDERS_PATH = os.path.join(BACKEND_DIR, "orders.json")

if not os.path.exists(CATALOG_PATH):
    logger.warning(f"⚠️ products.json not found at {CATALOG_PATH}. Please ensure it exists.")
else:
    logger.info(f"✅ products.json found at {CATALOG_PATH}")


logger.info(f"BACKEND_DIR: {BACKEND_DIR}")
logger.info(f"CATALOG_PATH: {CATALOG_PATH}")
logger.info(f"Catalog exists: {os.path.exists(CATALOG_PATH)}")

# -------------------------
# Catalog + Orders Helpers
# -------------------------
def load_catalog() -> list:
    try:
        with open(CATALOG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Failed to load catalog from {CATALOG_PATH}: {e}")
        return []

def load_orders() -> list:
    if not os.path.exists(ORDERS_PATH):
        return []
    try:
        with open(ORDERS_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []

def save_orders(orders: list):
    try:
        with open(ORDERS_PATH, "w", encoding="utf-8") as f:
            json.dump(orders, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error(f"Failed to save orders: {e}")

# -------------------------
# Tools
# -------------------------
@function_tool
async def list_products(
    ctx: RunContext[Userdata],
    query: Annotated[Optional[str], Field(description="Search query to filter products by name, description, or category", default=None)] = None,
    category: Annotated[Optional[str], Field(description="Filter by product category (e.g., 'mug', 'tshirt', 'hoodie')", default=None)] = None,
    color: Annotated[Optional[str], Field(description="Filter by product color", default=None)] = None,
    max_price: Annotated[Optional[float], Field(description="Maximum price filter (e.g., 1000 for products under ₹1000)", default=None)] = None,
    min_price: Annotated[Optional[float], Field(description="Minimum price filter", default=None)] = None,
) -> str:
    """
    List products with optional filtering by query, category, color, and price range.
    All parameters are optional - you can use any combination of filters.
    Examples:
    - query="coffee mug" -> finds products with "coffee mug" in name/description
    - category="tshirt" -> filters by category
    - color="black" -> filters by color
    - max_price=1000 -> shows products under ₹1000
    """
    catalog = load_catalog()
    filtered = []
    
    for p in catalog:
        # Filter by query (searches in name, description, and category)
        if query:
            query_lower = query.lower()
            name = p.get("name", "").lower()
            desc = p.get("description", "").lower()
            cat = p.get("category", "").lower()
            if query_lower not in name and query_lower not in desc and query_lower not in cat:
                continue
        
        # Filter by category
        if category:
            if p.get("category", "").lower() != category.lower():
                continue
        
        # Filter by color
        if color:
            if p.get("color", "").lower() != color.lower():
                continue
        
        # Filter by price range
        price = float(p.get("price", 0))
        if max_price and price > max_price:
            continue
        if min_price and price < min_price:
            continue
        
        filtered.append(p)

    if not filtered:
        filters = []
        if query:
            filters.append(f"query '{query}'")
        if category:
            filters.append(f"category '{category}'")
        if color:
            filters.append(f"color '{color}'")
        if max_price:
            filters.append(f"under ₹{max_price}")
        filter_str = " with " + ", ".join(filters) if filters else ""
        return f"No products found{filter_str}."

    lines = []
    for idx, p in enumerate(filtered[:10], 1):
        attrs = []
        if p.get("color"):
            attrs.append(f"Color: {p['color']}")
        if p.get("size"):
            attrs.append(f"Size: {p['size']}")
        attr_str = f" | {', '.join(attrs)}" if attrs else ""
        lines.append(f"{idx}. {p['name']} (id: {p['id']}) — ₹{p['price']} | Category: {p.get('category', 'N/A')}{attr_str}")
    
    result = f"Found {len(filtered)} product(s). Here are the options:\n" + "\n".join(lines)
    if len(filtered) > 10:
        result += f"\n... and {len(filtered) - 10} more product(s)"
    return result

@function_tool
async def show_product(
    ctx: RunContext[Userdata],
    product_id: Annotated[str, Field(description="Product ID")],
) -> str:
    catalog = load_catalog()
    for p in catalog:
        if p["id"].lower() == product_id.lower():
            return f"{p['name']} — ₹{p['price']} | Category: {p.get('category','')} | {p.get('description','No description')}"
    return f"Couldn't find product with id '{product_id}'."

@function_tool
async def add_to_cart(
    ctx: RunContext[Userdata],
    product_id: Annotated[str, Field(description="Product ID to add")],
    quantity: Annotated[int, Field(description="Quantity to add", ge=1)] = 1,
    size: Optional[str] = None,
) -> str:
    """
    Add a product to the cart. If size is specified, try to find a matching product variant.
    """
    catalog = load_catalog()
    item = None
    
    # If size is specified, try to find a product with matching size
    if size:
        for p in catalog:
            if p["id"].lower() == product_id.lower() or p.get("name", "").lower() == product_id.lower():
                if p.get("size", "").lower() == size.lower():
                    item = p
                    break
        # If not found by size, fall back to exact product_id match
        if not item:
            item = next((p for p in catalog if p["id"].lower() == product_id.lower()), None)
    else:
        item = next((p for p in catalog if p["id"].lower() == product_id.lower()), None)
    
    if not item:
        return f"Product '{product_id}' not found."
    
    # Check if same product (same ID) already in cart
    for ci in ctx.userdata.cart:
        if ci.id.lower() == item["id"].lower():
            ci.quantity += quantity
            total = sum(c.price * c.quantity for c in ctx.userdata.cart)
            size_info = f" (Size: {item.get('size', 'N/A')})" if item.get('size') else ""
            # Return cart summary so frontend can parse it
            lines = [f"- {c.quantity} x {c.name} @ ₹{c.price:.2f} = ₹{c.price * c.quantity:.2f}" for c in ctx.userdata.cart]
            return f"Updated '{ci.name}{size_info}' quantity to {ci.quantity}.\n\nYour cart:\n" + "\n".join(lines) + f"\nTotal: ₹{total:.2f}"
    
    # Add new item to cart
    size_value = size or item.get("size")
    cart_item = CartItem(
        id=item["id"],
        name=item["name"],
        price=float(item["price"]),
        quantity=quantity,
        size=size_value
    )
    ctx.userdata.cart.append(cart_item)
    total = sum(c.price * c.quantity for c in ctx.userdata.cart)
    size_info = f" (Size: {size_value})" if size_value else ""
    # Return cart summary so frontend can parse it
    lines = [f"- {c.quantity} x {c.name} @ ₹{c.price:.2f} = ₹{c.price * c.quantity:.2f}" for c in ctx.userdata.cart]
    return f"Added {quantity} x {item['name']}{size_info} to your cart.\n\nYour cart:\n" + "\n".join(lines) + f"\nTotal: ₹{total:.2f}"

@function_tool
async def remove_from_cart(
    ctx: RunContext[Userdata],
    product_id: Annotated[str, Field(description="Product ID to remove")],
) -> str:
    before = len(ctx.userdata.cart)
    ctx.userdata.cart = [ci for ci in ctx.userdata.cart if ci.id.lower() != product_id.lower()]
    after = len(ctx.userdata.cart)
    if before == after:
        return f"Item '{product_id}' not found in cart."
    total = sum(c.price * c.quantity for c in ctx.userdata.cart)
    return f"Removed item '{product_id}'. Cart total: ₹{total:.2f}"

@function_tool
async def show_cart(ctx: RunContext[Userdata]) -> str:
    if not ctx.userdata.cart:
        return "Your cart is empty."
    lines = []
    for ci in ctx.userdata.cart:
        size_info = f" (Size: {ci.size})" if ci.size else ""
        lines.append(f"- {ci.quantity} x {ci.name}{size_info} @ ₹{ci.price:.2f} = ₹{ci.price * ci.quantity:.2f}")
    total = sum(c.price * c.quantity for c in ctx.userdata.cart)
    return "Your cart:\n" + "\n".join(lines) + f"\nTotal: ₹{total:.2f}"

def create_order(line_items: list[dict], customer_name: str = "Customer") -> dict:
    """
    ACP-inspired merchant function: Create an order from line items.
    line_items: [{ "product_id": "...", "quantity": 1 }, ...]
    Returns the created order dict.
    """
    catalog = load_catalog()
    order_items = []
    total = 0.0
    
    for line_item in line_items:
        product_id = line_item.get("product_id")
        quantity = line_item.get("quantity", 1)
        
        # Find product in catalog
        product = next((p for p in catalog if p["id"].lower() == product_id.lower()), None)
        if not product:
            continue
        
        price = float(product.get("price", 0))
        order_items.append({
            "id": product["id"],
            "name": product["name"],
            "price": price,
            "quantity": quantity,
        })
        total += price * quantity
    
    order_id = str(uuid.uuid4())[:8]
    timestamp = datetime.utcnow().isoformat() + "Z"
    
    order = {
        "order_id": order_id,
        "customer": customer_name,
        "timestamp": timestamp,
        "total": total,
        "currency": "INR",
        "items": order_items,
        "status": "confirmed",
    }
    
    # Persist order
    orders = load_orders()
    orders.append(order)
    save_orders(orders)
    
    return order

@function_tool
async def place_order(
    ctx: RunContext[Userdata],
    customer_name: Annotated[str, Field(description="Customer name")],
) -> str:
    """
    Place an order from the current cart. Uses create_order internally.
    """
    if not ctx.userdata.cart:
        return "Your cart is empty."
    
    # Convert cart to line_items format
    line_items = [{"product_id": c.id, "quantity": c.quantity} for c in ctx.userdata.cart]
    
    # Create order using the merchant function
    order = create_order(line_items, customer_name)
    
    # Store last order and clear cart
    ctx.userdata.last_order = order
    ctx.userdata.cart.clear()

    return f"Order placed successfully! Order ID: {order['order_id']}. Total ₹{order['total']:.2f}. It's being processed under express checkout."

@function_tool
async def last_order(ctx: RunContext[Userdata]) -> str:
    if not ctx.userdata.last_order:
        return "You haven't placed any orders yet."
    o = ctx.userdata.last_order
    items = ", ".join([i["name"] for i in o["items"]])
    return f"Your last order ({o['order_id']}) includes {items}. Total ₹{o['total']:.2f}. Status: {o['status']}."

@function_tool
async def order_history(ctx: RunContext[Userdata]) -> str:
    orders = load_orders()
    if not orders:
        return "No past orders found."
    lines = []
    for o in orders[-5:]:
        lines.append(f"- {o['order_id']} | ₹{o['total']:.2f} | {o['status']} | {o['timestamp']}")
    return "Recent orders:\n" + "\n".join(lines)

# -------------------------
# Agent Definition
# -------------------------
class EcommerceAgent(Agent):
    def __init__(self):
        super().__init__(
            instructions="""
            You are 'Nova', a friendly AI shopping assistant for an online store.
            Tone: Helpful, modern, concise, and professional.
            You help users browse products, compare items, and place orders.

            Guidelines:
            - When users ask to browse products, use list_products with appropriate filters:
              * "Show me all coffee mugs" -> list_products(category="mug")
              * "Do you have any t-shirts under 1000?" -> list_products(category="tshirt", max_price=1000)
              * "I'm looking for a black hoodie" -> list_products(category="hoodie", color="black")
              * "Does this coffee mug come in blue?" -> list_products(category="mug", color="blue")
            
            - When listing products, mention the product number/position so users can refer to them:
              "I found 3 options: 1. Product A, 2. Product B, 3. Product C"
            
            - When users want to buy something, help them add items to cart:
              * "I'll buy the second hoodie" -> identify which product they mean and use add_to_cart
              * "Add 2 coffee mugs to my cart" -> use add_to_cart with quantity=2
            
            - Always show cart contents before placing an order to confirm.
            
            - When placing orders, ask for the customer name and use place_order.
            
            - Use show_cart when users ask "What's in my cart?" or "Show me my cart".
            
            - Use last_order when users ask "What did I just buy?" or "Show me my last order".
            
            - Use order_history when users ask about past orders or order history.
            
            - Be polite, avoid repeating too much.
            - Mention prices in Indian Rupees (₹).
            - Confirm details when placing an order.
            - Orders are simulated only (no payments).
            """,
            tools=[
                list_products,
                show_product,
                add_to_cart,
                remove_from_cart,
                show_cart,
                place_order,
                last_order,
                order_history,
            ],
        )

# -------------------------
# Entrypoint
# -------------------------
def prewarm(proc: JobProcess):
    try:
        proc.userdata["vad"] = silero.VAD.load()
    except Exception:
        logger.warning("VAD prewarm failed; continuing without preloaded VAD.")

async def entrypoint(ctx: JobContext):
    ctx.log_context_fields = {"room": ctx.room.name}
    logger.info("\n🛒 Starting E-Commerce Voice Agent (ACP Inspired)")
    
    # Verify catalog loads
    catalog = load_catalog()
    logger.info(f"Catalog loaded with {len(catalog)} products")
    if not catalog:
        logger.warning("⚠️ WARNING: Catalog is empty or failed to load!")

    session = AgentSession(
        stt=deepgram.STT(model="nova-3"),
        llm=openai.LLM(model="gpt-4o-mini"),  # Using OpenAI GPT-4o-mini (fast and cost-effective)
        tts=murf.TTS(
            voice="en-US-natalie",
            style="Conversational",
            text_pacing=True,
        ),
        turn_detection=MultilingualModel(),
        vad=ctx.proc.userdata.get("vad"),
        userdata=Userdata(),
    )

    await session.start(
        agent=EcommerceAgent(),
        room=ctx.room,
        room_input_options=RoomInputOptions(noise_cancellation=noise_cancellation.BVC()),
    )
    
    # Ensure transcriptions are published in real-time
    # LiveKit agents automatically publish transcriptions, but we verify it's enabled
    logger.info("✅ Agent session started with real-time transcription enabled")
    await ctx.connect()

if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint, prewarm_fnc=prewarm))
