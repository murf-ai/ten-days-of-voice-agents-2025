import logging
import json
import os
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from datetime import datetime

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
    """Load product catalog from JSON file."""
    try:
        with open(CATALOG_FILE, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        logger.error(f"Catalog file not found: {CATALOG_FILE}")
        return {"store_name": "Store", "categories": {}, "recipes": {}}

CATALOG = load_catalog()
STORE_NAME = CATALOG.get("store_name", "QuickMart")

# Flatten catalog for easy lookup
ALL_PRODUCTS = {}
for category, items in CATALOG.get("categories", {}).items():
    for item in items:
        ALL_PRODUCTS[item["id"]] = {**item, "category": category}

# --- Cart Management ---
@dataclass
class CartItem:
    """Represents an item in the cart."""
    product_id: str
    name: str
    quantity: int
    price: float
    unit: str
    
    def subtotal(self) -> float:
        return self.quantity * self.price

@dataclass
class ShoppingCart:
    """Manages the shopping cart."""
    items: List[CartItem] = field(default_factory=list)
    
    def add_item(self, product_id: str, quantity: int = 1) -> str:
        """Add item to cart."""
        if product_id not in ALL_PRODUCTS:
            return f"ERROR: Product {product_id} not found in catalog."
        
        product = ALL_PRODUCTS[product_id]
        
        # Check if already in cart
        for item in self.items:
            if item.product_id == product_id:
                item.quantity += quantity
                return f"UPDATED: Increased {product['name']} quantity to {item.quantity}"
        
        # Add new item
        self.items.append(CartItem(
            product_id=product_id,
            name=product["name"],
            quantity=quantity,
            price=product["price"],
            unit=product["unit"]
        ))
        return f"ADDED: {quantity}x {product['name']} ({product['unit']}) at ₹{product['price']} each"
    
    def remove_item(self, product_id: str) -> str:
        """Remove item from cart."""
        for i, item in enumerate(self.items):
            if item.product_id == product_id:
                removed = self.items.pop(i)
                return f"REMOVED: {removed.name} from cart"
        return f"ERROR: Item not found in cart"
    
    def update_quantity(self, product_id: str, new_quantity: int) -> str:
        """Update item quantity."""
        if new_quantity <= 0:
            return self.remove_item(product_id)
        
        for item in self.items:
            if item.product_id == product_id:
                old_qty = item.quantity
                item.quantity = new_quantity
                return f"UPDATED: {item.name} quantity from {old_qty} to {new_quantity}"
        return f"ERROR: Item not found in cart"
    
    def get_summary(self) -> Dict[str, Any]:
        """Get cart summary."""
        if not self.items:
            return {"empty": True, "total": 0, "items": []}
        
        total = sum(item.subtotal() for item in self.items)
        return {
            "empty": False,
            "total": total,
            "item_count": len(self.items),
            "items": [
                {
                    "name": item.name,
                    "quantity": item.quantity,
                    "unit": item.unit,
                    "price": item.price,
                    "subtotal": item.subtotal()
                }
                for item in self.items
            ]
        }
    
    def clear(self):
        """Clear the cart."""
        self.items = []

# --- Tools ---
@function_tool
async def search_products(
    context: RunContext,
    search_term: str,
    category: Optional[str] = None
) -> str:
    """
    Search for products in the catalog.
    
    Args:
        search_term: Product name or keyword to search for
        category: Optional category to filter by (groceries, snacks, beverages, prepared_food, cooking_ingredients)
    """
    search_term_lower = search_term.lower()
    results = []
    
    categories_to_search = [category] if category else CATALOG.get("categories", {}).keys()
    
    for cat in categories_to_search:
        for product in CATALOG.get("categories", {}).get(cat, []):
            if search_term_lower in product["name"].lower() or search_term_lower in product.get("brand", "").lower():
                results.append(f"{product['name']} ({product['brand']}) - ₹{product['price']} per {product['unit']} [ID: {product['id']}]")
    
    if not results:
        return f"PRODUCT_NOT_FOUND: No products found matching '{search_term}'."
    
    return "PRODUCTS_FOUND:\n" + "\n".join(results[:5])  # Limit to 5 results

@function_tool
async def add_to_cart(
    context: RunContext,
    product_id: str,
    quantity: int = 1
) -> str:
    """
    Add a product to the shopping cart.
    
    Args:
        product_id: The product ID from the catalog
        quantity: Number of units to add (default: 1)
    """
    cart: ShoppingCart = context.userdata["cart"]
    result = cart.add_item(product_id, quantity)
    context.userdata["cart"] = cart
    return result

@function_tool
async def add_recipe_ingredients(
    context: RunContext,
    recipe_name: str
) -> str:
    """
    Add all ingredients for a recipe/meal to the cart.
    
    Args:
        recipe_name: Name of the recipe (e.g., 'peanut butter sandwich', 'pasta for two', 'breakfast')
    """
    recipe_name_lower = recipe_name.lower()
    recipes = CATALOG.get("recipes", {})
    
    if recipe_name_lower not in recipes:
        available = ", ".join(recipes.keys())
        return f"RECIPE_NOT_FOUND: Recipe '{recipe_name}' not found. Available recipes: {available}"
    
    cart: ShoppingCart = context.userdata["cart"]
    product_ids = recipes[recipe_name_lower]
    added_items = []
    
    for product_id in product_ids:
        if product_id in ALL_PRODUCTS:
            cart.add_item(product_id, quantity=1)
            added_items.append(ALL_PRODUCTS[product_id]["name"])
    
    context.userdata["cart"] = cart
    return f"RECIPE_ADDED: Added {', '.join(added_items)} for '{recipe_name}'"

@function_tool
async def remove_from_cart(
    context: RunContext,
    product_id: str
) -> str:
    """
    Remove a product from the shopping cart.
    
    Args:
        product_id: The product ID to remove
    """
    cart: ShoppingCart = context.userdata["cart"]
    result = cart.remove_item(product_id)
    context.userdata["cart"] = cart
    return result

@function_tool
async def update_cart_quantity(
    context: RunContext,
    product_id: str,
    new_quantity: int
) -> str:
    """
    Update the quantity of an item in the cart.
    
    Args:
        product_id: The product ID
        new_quantity: New quantity (0 to remove)
    """
    cart: ShoppingCart = context.userdata["cart"]
    result = cart.update_quantity(product_id, new_quantity)
    context.userdata["cart"] = cart
    return result

@function_tool
async def view_cart(
    context: RunContext
) -> str:
    """
    View the current shopping cart contents and total.
    """
    cart: ShoppingCart = context.userdata["cart"]
    summary = cart.get_summary()
    
    if summary["empty"]:
        return "CART_EMPTY: Your cart is empty. Browse products and add items!"
    
    cart_text = f"CART_SUMMARY:\n"
    for item in summary["items"]:
        cart_text += f"• {item['quantity']}x {item['name']} ({item['unit']}) - ₹{item['subtotal']}\n"
    cart_text += f"\nTotal: ₹{summary['total']}"
    
    return cart_text

@function_tool
async def place_order(
    context: RunContext,
    customer_name: str,
    delivery_address: str
) -> str:
    """
    Place the order and save it to a file.
    
    Args:
        customer_name: Customer's name
        delivery_address: Delivery address
    """
    cart: ShoppingCart = context.userdata["cart"]
    summary = cart.get_summary()
    
    if summary["empty"]:
        return "ERROR: Cannot place order. Cart is empty."
    
    # Create order
    order = {
        "order_id": f"ORD_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        "customer_name": customer_name,
        "delivery_address": delivery_address,
        "timestamp": datetime.now().isoformat(),
        "items": summary["items"],
        "total": summary["total"],
        "status": "placed"
    }
    
    # Save to file
    filename = f"order_{order['order_id']}.json"
    with open(filename, 'w') as f:
        json.dump(order, f, indent=2)
    
    logger.info(f"Order placed: {filename}")
    
    # Clear cart
    cart.clear()
    context.userdata["cart"] = cart
    
    return (
        f"ORDER_PLACED: Order {order['order_id']} confirmed! "
        f"Total: ₹{order['total']}. "
        f"Your order will be delivered to {delivery_address} within 30 minutes. "
        f"Order saved to {filename}."
    )

# --- Shopping Assistant Agent ---
class ShoppingAssistant(Agent):
    """Food and grocery ordering voice agent."""
    
    def __init__(self, llm) -> None:
        super().__init__(
            instructions=(
                f"You are a friendly shopping assistant for {STORE_NAME}, a quick commerce platform. "
                "\n\n"
                f"**GREETING:** 'Hi! Welcome to {STORE_NAME}! I can help you order groceries, snacks, and prepared food. "
                "You can ask me to search for items, add them to your cart, or even say things like "
                "'I need ingredients for a sandwich' and I'll add everything you need!' "
                "\n\n"
                "**HOW TO HELP:**\n"
                "1. **Search Products:** Use search_products when user asks for items\n"
                "2. **Add to Cart:** Use add_to_cart with product_id and quantity\n"
                "3. **Recipe Requests:** If user says 'ingredients for X', use add_recipe_ingredients\n"
                "4. **Manage Cart:** Use remove_from_cart, update_cart_quantity, or view_cart as needed\n"
                "5. **Place Order:** When user says 'place order' or 'checkout', ask for name and address, then use place_order\n"
                "\n"
                "**AVAILABLE RECIPES:** peanut butter sandwich, pasta for two, breakfast, tea time\n"
                "\n"
                "**TIPS:**\n"
                "- Always confirm what you're adding to the cart\n"
                "- When showing cart, read the total clearly\n"
                "- Ask clarifying questions if needed (size, brand, quantity)\n"
                "- Be concise but friendly\n"
            ),
            tools=[
                search_products,
                add_to_cart,
                add_recipe_ingredients,
                remove_from_cart,
                update_cart_quantity,
                view_cart,
                place_order
            ],
            llm=llm
        )

# --- Entrypoint ---
async def entrypoint(ctx: JobContext):
    """Main entrypoint for shopping assistant."""
    
    # Initialize cart
    cart = ShoppingCart()
    
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
    
    session.userdata = {"cart": cart}
    
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
    await session.start(agent=ShoppingAssistant(llm=llm), room=ctx.room)
    await ctx.connect()

def prewarm(proc: JobProcess):
    """Preload resources."""
    pass

if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint, prewarm_fnc=prewarm))
