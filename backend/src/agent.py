import logging
import json
import os
from dataclasses import dataclass, field, asdict
from typing import Optional, List, Dict, Any
from datetime import datetime
import uuid

from dotenv import load_dotenv
from livekit.agents import (
    Agent,
    AgentSession,
    JobContext,
    JobProcess,
    MetricsCollectedEvent,
    WorkerOptions,
    cli,
    metrics,
    tokenize,
    function_tool,
    RunContext
)
from livekit.plugins import murf, silero, google, deepgram
from livekit.plugins.turn_detector.multilingual import MultilingualModel

logger = logging.getLogger("agent")
load_dotenv(".env.local")

# --- Load Catalog ---
CATALOG_FILE = "catalog.json"

def load_catalog():
    """Load product catalog from JSON."""
    try:
        with open(CATALOG_FILE, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        logger.error(f"Catalog not found: {CATALOG_FILE}")
        return {"store_name": "Store", "currency": "INR", "products": []}

CATALOG = load_catalog()
STORE_NAME = CATALOG.get("store_name", "Store")
CURRENCY = CATALOG.get("currency", "INR")
PRODUCTS = {p["id"]: p for p in CATALOG.get("products", [])}

# --- ACP-Inspired Data Models ---
@dataclass
class LineItem:
    """Represents a single item in an order."""
    product_id: str
    product_name: str
    quantity: int
    unit_price: float
    size: Optional[str] = None
    color: Optional[str] = None
    
    def subtotal(self) -> float:
        return self.quantity * self.unit_price

@dataclass
class Order:
    """ACP-inspired order structure."""
    order_id: str
    line_items: List[LineItem]
    total: float
    currency: str
    status: str = "PENDING"  # PENDING, CONFIRMED, CANCELLED
    buyer_name: Optional[str] = None
    buyer_email: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def get_summary(self) -> Dict[str, Any]:
        return {
            "order_id": self.order_id,
            "items": [
                {
                    "name": item.product_name,
                    "quantity": item.quantity,
                    "size": item.size,
                    "price": item.unit_price,
                    "subtotal": item.subtotal()
                }
                for item in self.line_items
            ],
            "total": self.total,
            "currency": self.currency,
            "status": self.status,
            "created_at": self.created_at
        }

@dataclass
class ShoppingCart:
    """Shopping cart for building orders."""
    items: List[LineItem] = field(default_factory=list)
    
    def add_item(self, product_id: str, quantity: int = 1, size: Optional[str] = None) -> str:
        """Add item to cart."""
        if product_id not in PRODUCTS:
            return f"ERROR: Product {product_id} not found"
        
        product = PRODUCTS[product_id]
        
        # Check if already in cart
        for item in self.items:
            if item.product_id == product_id and item.size == size:
                item.quantity += quantity
                return f"UPDATED: {product['name']} quantity to {item.quantity}"
        
        # Add new item
        self.items.append(LineItem(
            product_id=product_id,
            product_name=product["name"],
            quantity=quantity,
            unit_price=product["price"],
            size=size,
            color=product.get("color")
        ))
        return f"ADDED: {quantity}x {product['name']} (₹{product['price']})"
    
    def remove_item(self, product_id: str) -> str:
        """Remove item from cart."""
        for i, item in enumerate(self.items):
            if item.product_id == product_id:
                removed = self.items.pop(i)
                return f"REMOVED: {removed.product_name}"
        return "ERROR: Item not in cart"
    
    def get_total(self) -> float:
        """Calculate cart total."""
        return sum(item.subtotal() for item in self.items)
    
    def clear(self):
        """Clear the cart."""
        self.items = []
    
    def is_empty(self) -> bool:
        """Check if cart is empty."""
        return len(self.items) == 0

# --- Commerce Functions (ACP-Inspired Merchant Layer) ---
def list_products(
    category: Optional[str] = None,
    max_price: Optional[int] = None,
    color: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Browse product catalog with filters.
    
    Args:
        category: Filter by category
        max_price: Maximum price filter
        color: Filter by color
    """
    results = CATALOG.get("products", [])
    
    if category:
        results = [p for p in results if p.get("category") == category.lower()]
    
    if max_price:
        results = [p for p in results if p.get("price", 0) <= max_price]
    
    if color:
        results = [p for p in results if p.get("color", "").lower() == color.lower()]
    
    return results

def create_order(
    cart: ShoppingCart,
    buyer_name: Optional[str] = None,
    buyer_email: Optional[str] = None
) -> Order:
    """
    Create an order from cart contents.
    
    Args:
        cart: Shopping cart with line items
        buyer_name: Customer name
        buyer_email: Customer email
    """
    order = Order(
        order_id=f"ORD-{uuid.uuid4().hex[:8].upper()}",
        line_items=cart.items.copy(),
        total=cart.get_total(),
        currency=CURRENCY,
        status="CONFIRMED",
        buyer_name=buyer_name,
        buyer_email=buyer_email
    )
    
    # Save order to file
    filename = f"order_{order.order_id}.json"
    with open(filename, 'w') as f:
        json.dump(order.get_summary(), f, indent=2)
    
    logger.info(f"Order created: {order.order_id}")
    
    return order

# --- Agent Tools ---
@function_tool
async def browse_catalog(
    context: RunContext,
    category: Optional[str] = None,
    max_price: Optional[int] = None,
    color: Optional[str] = None
) -> str:
    """
    Browse the product catalog with optional filters.
    
    Args:
        category: Product category (hoodies, tshirts, accessories, bottoms, jackets, sweatshirts)
        max_price: Maximum price in INR
        color: Color filter
    """
    products = list_products(category=category, max_price=max_price, color=color)
    
    if not products:
        return "NO_RESULTS: No products found matching your criteria"
    
    result = f"PRODUCTS_FOUND ({len(products)} items):\n"
    for i, p in enumerate(products[:5], 1):  # Limit to 5 results
        sizes = ", ".join(p.get("sizes", []))
        result += f"{i}. {p['name']} - ₹{p['price']} ({p['color']}, sizes: {sizes}) [ID: {p['id']}]\n"
    
    if len(products) > 5:
        result += f"... and {len(products) - 5} more items"
    
    return result

@function_tool
async def add_to_cart(
    context: RunContext,
    product_id: str,
    quantity: int = 1,
    size: Optional[str] = None
) -> str:
    """
    Add a product to the shopping cart.
    
    Args:
        product_id: Product ID from catalog
        quantity: Quantity to add
        size: Size selection (S, M, L, XL, etc)
    """
    cart: ShoppingCart = context.userdata["cart"]
    result = cart.add_item(product_id, quantity, size)
    context.userdata["cart"] = cart
    return result

@function_tool
async def remove_from_cart(
    context: RunContext,
    product_id: str
) -> str:
    """
    Remove a product from the cart.
    
    Args:
        product_id: Product ID to remove
    """
    cart: ShoppingCart = context.userdata["cart"]
    result = cart.remove_item(product_id)
    context.userdata["cart"] = cart
    return result

@function_tool
async def view_cart(
    context: RunContext
) -> str:
    """View current shopping cart contents."""
    cart: ShoppingCart = context.userdata["cart"]
    
    if cart.is_empty():
        return "CART_EMPTY: Your cart is empty. Browse products to get started!"
    
    cart_text = "CART_CONTENTS:\n"
    for item in cart.items:
        size_info = f" (Size: {item.size})" if item.size else ""
        cart_text += f"• {item.quantity}x {item.product_name}{size_info} - ₹{item.subtotal()}\n"
    
    cart_text += f"\nTotal: ₹{cart.get_total()}"
    return cart_text

@function_tool
async def checkout(
    context: RunContext,
    buyer_name: str,
    buyer_email: Optional[str] = None
) -> str:
    """
    Checkout and create an order from cart contents.
    
    Args:
        buyer_name: Customer's name
        buyer_email: Customer's email (optional)
    """
    cart: ShoppingCart = context.userdata["cart"]
    
    if cart.is_empty():
        return "ERROR: Cannot checkout with empty cart"
    
    # Create order
    order = create_order(cart, buyer_name, buyer_email)
    
    # Store in session
    orders: List[Order] = context.userdata.get("orders", [])
    orders.append(order)
    context.userdata["orders"] = orders
    
    # Clear cart
    cart.clear()
    context.userdata["cart"] = cart
    
    return (
        f"ORDER_CONFIRMED: Order {order.order_id} placed successfully!\n"
        f"Total: ₹{order.total}\n"
        f"Items: {len(order.line_items)}\n"
        f"Order saved to order_{order.order_id}.json"
    )

@function_tool
async def view_last_order(
    context: RunContext
) -> str:
    """View the most recent order."""
    orders: List[Order] = context.userdata.get("orders", [])
    
    if not orders:
        return "NO_ORDERS: You haven't placed any orders yet"
    
    order = orders[-1]
    summary = order.get_summary()
    
    result = f"LAST_ORDER ({order.order_id}):\n"
    for item in summary["items"]:
        size_info = f" (Size: {item['size']})" if item['size'] else ""
        result += f"• {item['quantity']}x {item['name']}{size_info} - ₹{item['subtotal']}\n"
    
    result += f"\nTotal: ₹{summary['total']}\nStatus: {order.status}"
    return result

# --- Commerce Agent ---
class CommerceAgent(Agent):
    """ACP-inspired voice commerce agent."""
    
    def __init__(self, llm) -> None:
        super().__init__(
            instructions=(
                f"You are a helpful shopping assistant for {STORE_NAME}, an Indian streetwear brand. "
                "\n\n"
                f"**GREETING:** 'Hey! Welcome to {STORE_NAME}! We've got hoodies, tees, joggers, and more. "
                "What are you looking for today?'"
                "\n\n"
                "**HOW TO HELP:**\n"
                "1. **Browse:** Use browse_catalog when user asks about products\n"
                "   - Categories: hoodies, tshirts, accessories, bottoms, jackets, sweatshirts\n"
                "   - Can filter by category, price, color\n"
                "2. **Add to Cart:** Use add_to_cart with product_id, quantity, and size\n"
                "   - ALWAYS ask for size if the product has sizes\n"
                "3. **Manage Cart:** Use remove_from_cart or view_cart as needed\n"
                "4. **Checkout:** When user says 'checkout' or 'place order', ask for name and use checkout\n"
                "5. **Order Info:** Use view_last_order when user asks about their order\n"
                "\n\n"
                "**IMPORTANT:**\n"
                "- Always confirm what you're adding to cart\n"
                "- Ask for size when needed (S, M, L, XL)\n"
                "- Be helpful with product recommendations\n"
                "- Keep responses conversational and brief\n"
                "- All prices are in Indian Rupees (₹)\n"
            ),
            tools=[
                browse_catalog,
                add_to_cart,
                remove_from_cart,
                view_cart,
                checkout,
                view_last_order
            ],
            llm=llm
        )

# --- Entrypoint ---
async def entrypoint(ctx: JobContext):
    """Main entrypoint."""
    
    # Initialize cart and orders
    cart = ShoppingCart()
    orders = []
    
    ctx.log_context_fields = {"room": ctx.room.name}
    llm = google.LLM(model="gemini-2.5-flash")
    
    session = AgentSession(
        stt=deepgram.STT(model="nova-3"),
        llm=llm,
        tts=murf.TTS(
            voice="en-US-alicia",
            style="Conversation",
            tokenizer=tokenize.basic.SentenceTokenizer(min_sentence_len=2),
            text_pacing=True
        ),
        turn_detection=MultilingualModel(),
        vad=silero.VAD.load(),
        preemptive_generation=True,
    )
    
    session.userdata = {"cart": cart, "orders": orders}
    
    # Metrics
    usage_collector = metrics.UsageCollector()
    
    @session.on("metrics_collected")
    def _on_metrics_collected(ev: MetricsCollectedEvent):
        metrics.log_metrics(ev.metrics)
        usage_collector.collect(ev.metrics)
    
    async def log_usage():
        summary = usage_collector.get_summary()
        logger.info(f"Usage: {summary}")
    
    ctx.add_shutdown_callback(log_usage)
    
    # Start session
    await session.start(agent=CommerceAgent(llm=llm), room=ctx.room)
    await ctx.connect()

def prewarm(proc: JobProcess):
    """Preload resources."""
    pass

if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint, prewarm_fnc=prewarm))
