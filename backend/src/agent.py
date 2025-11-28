import logging
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional

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

# ------------ Catalog & Order Management ------------

CATALOG_FILE = Path(__file__).parent.parent / "shared-data" / "day7_catalog.json"
ORDERS_DIR = Path(__file__).parent.parent / "orders"

class GroceryCatalog:
    def __init__(self):
        self.data = self._load_catalog()
        self.store_name = self.data.get("store_name", "DesiMart")
        self.items = {item["id"]: item for item in self.data.get("items", [])}
        self.recipes = self.data.get("recipes", {})
    
    def _load_catalog(self):
        """Load catalog from JSON"""
        if not CATALOG_FILE.exists():
            logger.error(f"Catalog file not found: {CATALOG_FILE}")
            CATALOG_FILE.parent.mkdir(parents=True, exist_ok=True)
            default_catalog = {
                "store_name": "DesiMart Express",
                "items": [],
                "recipes": {}
            }
            with open(CATALOG_FILE, "w") as f:
                json.dump(default_catalog, f, indent=2)
            return default_catalog
        
        try:
            with open(CATALOG_FILE, "r") as f:
                return json.load(f)
        except json.JSONDecodeError as e:
            logger.error(f"Error parsing catalog: {e}")
            return {"store_name": "DesiMart", "items": [], "recipes": {}}
    
    def search_items(self, query: str) -> List[dict]:
        """Search items by name, category, or tags"""
        query_lower = query.lower()
        results = []
        
        for item in self.items.values():
            if query_lower in item["name"].lower() or \
               query_lower in item["category"].lower() or \
               any(query_lower in tag for tag in item.get("tags", [])):
                results.append(item)
        
        return results
    
    def get_item_by_id(self, item_id: str) -> Optional[dict]:
        """Get item by ID"""
        return self.items.get(item_id)
    
    def get_recipe_items(self, recipe_name: str) -> List[str]:
        """Get item IDs for a recipe"""
        recipe_lower = recipe_name.lower()
        return self.recipes.get(recipe_lower, [])
    
    def get_items_by_ids(self, item_ids: List[str]) -> List[dict]:
        """Get multiple items by IDs"""
        return [self.items[item_id] for item_id in item_ids if item_id in self.items]

class ShoppingCart:
    def __init__(self):
        self.items: Dict[str, dict] = {}  # item_id -> {item_data, quantity}
    
    def add_item(self, item: dict, quantity: int = 1):
        """Add item to cart"""
        item_id = item["id"]
        if item_id in self.items:
            self.items[item_id]["quantity"] += quantity
        else:
            self.items[item_id] = {
                **item,
                "quantity": quantity
            }
        logger.info(f"Added {quantity}x {item['name']} to cart")
    
    def remove_item(self, item_id: str):
        """Remove item from cart"""
        if item_id in self.items:
            removed = self.items.pop(item_id)
            logger.info(f"Removed {removed['name']} from cart")
            return True
        return False
    
    def update_quantity(self, item_id: str, quantity: int):
        """Update item quantity"""
        if item_id in self.items:
            if quantity <= 0:
                return self.remove_item(item_id)
            self.items[item_id]["quantity"] = quantity
            logger.info(f"Updated {self.items[item_id]['name']} quantity to {quantity}")
            return True
        return False
    
    def get_cart_summary(self) -> dict:
        """Get cart summary with total"""
        total = sum(item["price"] * item["quantity"] for item in self.items.values())
        return {
            "items": list(self.items.values()),
            "item_count": sum(item["quantity"] for item in self.items.values()),
            "total": total
        }
    
    def clear(self):
        """Clear cart"""
        self.items.clear()
    
    def is_empty(self) -> bool:
        """Check if cart is empty"""
        return len(self.items) == 0

class OrderManager:
    def __init__(self):
        ORDERS_DIR.mkdir(parents=True, exist_ok=True)
    
    def save_order(self, cart: ShoppingCart, customer_name: str = "Customer", delivery_address: str = ""):
        """Save order to JSON file"""
        order_id = f"ORD{datetime.now().strftime('%Y%m%d%H%M%S')}"
        cart_summary = cart.get_cart_summary()
        
        order_data = {
            "order_id": order_id,
            "customer_name": customer_name,
            "delivery_address": delivery_address,
            "items": cart_summary["items"],
            "total_items": cart_summary["item_count"],
            "total_amount": cart_summary["total"],
            "order_time": datetime.now().isoformat(),
            "status": "placed",
            "estimated_delivery": "10 minutes"
        }
        
        # Save to file
        order_file = ORDERS_DIR / f"{order_id}.json"
        with open(order_file, "w") as f:
            json.dump(order_data, f, indent=2)
        
        logger.info(f"Order {order_id} saved: ₹{order_data['total_amount']}")
        return order_data

# ------------ Food Ordering Agent ------------

class FoodOrderingAgent(Agent):
    """Food & Grocery Ordering Voice Agent"""
    def __init__(self, catalog: GroceryCatalog):
        self.catalog = catalog
        self.cart = ShoppingCart()
        self.customer_name = ""
        self.delivery_address = ""
        self.order_manager = OrderManager()
        
        super().__init__(
            instructions=f"""
You are a friendly and enthusiastic food & grocery ordering assistant for {catalog.store_name}.

**Your Personality:**
- Warm, helpful, and conversational
- Use casual Indian English (like "acha", "theek hai", "perfect")
- Excited about helping customers
- Suggest popular combos and deals

**Your Role:**
Help customers order groceries, snacks, instant foods, and beverages through natural voice conversation.

**Capabilities:**

1. **Product Search & Information**
   - Help find items: "Do you have Maggi?" "Show me chips"
   - Provide details: price, brand, size
   - Suggest alternatives: "We have Yippee noodles too!"

2. **Smart Recipe-Based Ordering** (MOST IMPORTANT!)
   - Understand requests like:
     * "I need stuff for Maggi" → Add Maggi + milk
     * "Chai and snacks" → Add tea, milk, Parle-G
     * "Movie night essentials" → Add chips, cold drink, cookies
     * "Late night study snacks" → Add Maggi, Parle-G, chai, milk
     * "Dal chawal ingredients" → Add dal, rice, ghee
   
   - Use the 'add_recipe_items' function for these requests
   - Confirm what was added: "Perfect! I've added Maggi and milk for your late night craving!"

3. **Cart Management**
   - Add items with quantities: "2 packets of Maggi"
   - Remove items: "Remove the Kurkure"
   - Update quantities: "Make it 3 Frooti instead"
   - Show cart: "What's in my cart?"
   
4. **Checkout Process**
   - When user says "done", "place order", "checkout", or "that's all":
     * Ask for their name (if not already collected)
     * Ask for delivery address
     * Show final cart summary with total
     * Confirm and place order
   - Use 'place_order' function to finalize

**Conversation Flow:**

**START:**
"Namaste! Welcome to {catalog.store_name}! Ghar ka saman, 10 minute mein! 
What would you like to order today?"

**DURING ORDERING:**
- Be proactive: "Would you like some Parle-G with that chai?"
- Confirm additions: "Added! Anything else?"
- Natural responses: "Acha, theek hai", "Perfect choice!", "Great!"

**CHECKOUT:**
User: "That's all" or "Place my order"
You: "Great! Can I have your name for the order?"
User: "Suyash"
You: "Thanks Suyash! And what's your delivery address?"
User: "Raipur, Telibandha"
You: [Show cart summary + total]
You: "Shall I place this order for you?"
User: "Yes"
You: [Use place_order function]

**Important Guidelines:**
- Always confirm what was added to cart
- Suggest combos: "Maggi ke saath Frooti bhi lena hai?"
- Be enthusiastic about popular items: "Ah, Parle-G! Classic choice!"
- Use Indian pricing: "Only ₹20!", "₹240 ki chai, bahut time chalegi"
- Keep it conversational and fun!

**Function Tools Available:**
- search_catalog(query) - Find items
- add_to_cart(item_name, quantity) - Add specific items
- add_recipe_items(recipe_name) - Add bundled items for recipes
- remove_from_cart(item_name) - Remove items
- update_quantity(item_name, quantity) - Change quantity
- show_cart() - Display current cart
- place_order(customer_name, address) - Finalize order

Let's make grocery shopping fun and easy! 🛒
""",
        )
    
    @function_tool
    async def search_catalog(self, context: RunContext, query: str):
        """
        Search for items in the catalog by name, category, or tags.
        
        Args:
            query: Search term (e.g., "maggi", "chips", "chai", "milk")
        """
        logger.info(f"Searching catalog for: {query}")
        
        results = self.catalog.search_items(query)
        
        if not results:
            return f"Sorry, I couldn't find '{query}' in our catalog. Try searching for something else like Maggi, Parle-G, or Amul products!"
        
        # Format results
        if len(results) == 1:
            item = results[0]
            return f"Found {item['name']} by {item['brand']} - ₹{item['price']} for {item['unit']}. Should I add it to your cart?"
        
        elif len(results) <= 5:
            items_text = "\n".join([
                f"- {item['name']} ({item['brand']}) - ₹{item['price']} for {item['unit']}"
                for item in results
            ])
            return f"Here's what I found:\n{items_text}\n\nWhich one would you like?"
        
        else:
            items_text = "\n".join([
                f"- {item['name']} - ₹{item['price']}"
                for item in results[:5]
            ])
            return f"Found {len(results)} items! Here are the top ones:\n{items_text}\n\nWould you like to see more or add any of these?"
    
    @function_tool
    async def add_to_cart(self, context: RunContext, item_name: str, quantity: int = 1):
        """
        Add a specific item to the cart.
        
        Args:
            item_name: Name of the item to add
            quantity: How many to add (default: 1)
        """
        logger.info(f"Adding to cart: {item_name} x{quantity}")
        
        # Search for the item
        results = self.catalog.search_items(item_name)
        
        if not results:
            return f"Sorry, I couldn't find '{item_name}'. Try searching for it first!"
        
        # If multiple results, pick the closest match
        item = results[0]
        
        # Add to cart
        self.cart.add_item(item, quantity)
        
        total_price = item['price'] * quantity
        return f"Added {quantity}x {item['name']} ({item['brand']}) to your cart! That's ₹{total_price}. Anything else?"
    
    @function_tool
    async def add_recipe_items(self, context: RunContext, recipe_name: str):
        """
        Add all items needed for a recipe or combo (e.g., "maggi", "chai", "movie snacks").
        This is for requests like "I need stuff for Maggi" or "chai and snacks".
        
        Args:
            recipe_name: Name of recipe/combo (e.g., "maggi", "chai", "movie night", "study snacks")
        """
        logger.info(f"Adding recipe items for: {recipe_name}")
        
        # Get recipe item IDs
        item_ids = self.catalog.get_recipe_items(recipe_name)
        
        if not item_ids:
            # Try to be helpful with suggestions
            available_recipes = list(self.catalog.recipes.keys())
            suggestions = ", ".join(available_recipes[:5])
            return f"I don't have a preset for '{recipe_name}'. But I can help with: {suggestions}. What would you like?"
        
        # Get items and add to cart
        items = self.catalog.get_items_by_ids(item_ids)
        
        if not items:
            return "Oops, couldn't find those items. Let me know what you need!"
        
        # Add all items
        for item in items:
            self.cart.add_item(item, quantity=1)
        
        # Create response
        items_list = ", ".join([item['name'] for item in items])
        total = sum(item['price'] for item in items)
        
        return f"Perfect! I've added everything you need for {recipe_name}: {items_list}. Total: ₹{total}. Anything else?"
    
    @function_tool
    async def remove_from_cart(self, context: RunContext, item_name: str):
        """
        Remove an item from the cart.
        
        Args:
            item_name: Name of the item to remove
        """
        logger.info(f"Removing from cart: {item_name}")
        
        # Find item in cart
        for item_id, cart_item in self.cart.items.items():
            if item_name.lower() in cart_item['name'].lower():
                self.cart.remove_item(item_id)
                return f"Removed {cart_item['name']} from your cart. Anything else?"
        
        return f"I couldn't find '{item_name}' in your cart. Want to see what's in your cart?"
    
    @function_tool
    async def update_quantity(self, context: RunContext, item_name: str, quantity: int):
        """
        Update the quantity of an item in the cart.
        
        Args:
            item_name: Name of the item
            quantity: New quantity (use 0 to remove)
        """
        logger.info(f"Updating quantity: {item_name} to {quantity}")
        
        # Find item in cart
        for item_id, cart_item in self.cart.items.items():
            if item_name.lower() in cart_item['name'].lower():
                if quantity == 0:
                    self.cart.remove_item(item_id)
                    return f"Removed {cart_item['name']} from your cart."
                else:
                    self.cart.update_quantity(item_id, quantity)
                    new_price = cart_item['price'] * quantity
                    return f"Updated {cart_item['name']} to {quantity} pieces. That's ₹{new_price} now."
        
        return f"I couldn't find '{item_name}' in your cart. Want to add it?"
    
    @function_tool
    async def show_cart(self, context: RunContext):
        """
        Show all items currently in the shopping cart with quantities and prices.
        """
        logger.info("Showing cart contents")
        
        if self.cart.is_empty():
            return "Your cart is empty right now! What would you like to order?"
        
        cart_summary = self.cart.get_cart_summary()
        
        # Build cart display
        cart_text = "📦 **Your Cart:**\n\n"
        for item in cart_summary["items"]:
            item_total = item['price'] * item['quantity']
            cart_text += f"• {item['quantity']}x {item['name']} ({item['brand']}) - ₹{item_total}\n"
        
        cart_text += f"\n**Total Items:** {cart_summary['item_count']}"
        cart_text += f"\n**Total Amount:** ₹{cart_summary['total']}"
        cart_text += f"\n\nReady to checkout or want to add more items?"
        
        return cart_text
    
    @function_tool
    async def place_order(self, context: RunContext, customer_name: str = "", delivery_address: str = ""):
        """
        Place the final order and save it to a JSON file.
        
        Args:
            customer_name: Customer's name
            delivery_address: Delivery address
        """
        logger.info(f"Placing order for {customer_name}")
        
        if self.cart.is_empty():
            return "Your cart is empty! Add some items before placing the order."
        
        if not customer_name:
            return "I need your name to place the order. What's your name?"
        
        if not delivery_address:
            return "Great! And what's your delivery address?"
        
        # Save customer info
        self.customer_name = customer_name
        self.delivery_address = delivery_address
        
        # Get cart summary
        cart_summary = self.cart.get_cart_summary()
        
        # Save order
        order_data = self.order_manager.save_order(
            cart=self.cart,
            customer_name=customer_name,
            delivery_address=delivery_address
        )
        
        # Clear cart
        self.cart.clear()
        
        # Generate confirmation message
        response = f"""🎉 **Order Placed Successfully!**

**Order ID:** {order_data['order_id']}
**Customer:** {customer_name}
**Delivery Address:** {delivery_address}

**Order Summary:**
"""
        for item in order_data["items"]:
            response += f"• {item['quantity']}x {item['name']} - ₹{item['price'] * item['quantity']}\n"
        
        response += f"""
**Total Items:** {order_data['total_items']}
**Total Amount:** ₹{order_data['total_amount']}

**Estimated Delivery:** 10 minutes! 🚀

Thank you for ordering from {self.catalog.store_name}! Your order will reach you soon. 
Track your order with ID: {order_data['order_id']}

Anything else I can help you with?"""
        
        return response
    
    @function_tool
    async def save_customer_info(self, context: RunContext, name: str = "", address: str = ""):
        """
        Save customer name and address for checkout.
        
        Args:
            name: Customer's name
            address: Delivery address
        """
        if name:
            self.customer_name = name
        if address:
            self.delivery_address = address
        
        if self.customer_name and self.delivery_address:
            return f"Got it! {self.customer_name} at {self.delivery_address}. Ready to place your order?"
        elif self.customer_name:
            return f"Thanks {self.customer_name}! What's your delivery address?"
        elif self.delivery_address:
            return f"Address noted: {self.delivery_address}. What's your name?"
        else:
            return "I need your name and address to complete the order."

# ------------ Prewarm and Entrypoint ------------

def prewarm(proc: JobProcess):
    """Prewarm function to load models and catalog"""
    proc.userdata["vad"] = silero.VAD.load()
    
    # Preload catalog
    catalog = GroceryCatalog()
    proc.userdata["catalog"] = catalog
    logger.info(f"Prewarmed catalog for {catalog.store_name} with {len(catalog.items)} items")

async def entrypoint(ctx: JobContext):
    # Logging setup
    ctx.log_context_fields = {
        "room": ctx.room.name,
    }
    
    logger.info("🛒 Starting Food Ordering Agent...")
    
    # Load catalog from prewarm or create new
    if "catalog" in ctx.proc.userdata:
        catalog = ctx.proc.userdata["catalog"]
        logger.info(f"Using prewarmed catalog for {catalog.store_name}")
    else:
        catalog = GroceryCatalog()
        logger.info(f"Created new catalog for {catalog.store_name}")

    # Voice agent session pipeline
    session = AgentSession(
        stt=deepgram.STT(model="nova-3"),
        llm=google.LLM(model="gemini-2.5-flash"),
        tts=murf.TTS(
            voice="Alicia",  # Friendly, enthusiastic voice for shopping
            style="Conversation",
            tokenizer=tokenize.basic.SentenceTokenizer(min_sentence_len=2),
            text_pacing=True,
        ),
        turn_detection=MultilingualModel(),
        vad=ctx.proc.userdata["vad"],
        preemptive_generation=True,
    )

    # Metrics collection
    usage_collector = metrics.UsageCollector()
    
    @session.on("metrics_collected")
    def _on_metrics_collected(ev: MetricsCollectedEvent):
        metrics.log_metrics(ev.metrics)
        usage_collector.collect(ev.metrics)
    
    async def log_usage():
        summary = usage_collector.get_summary()
        logger.info(f"Usage: {summary}")
    
    ctx.add_shutdown_callback(log_usage)

    # Start session with Food Ordering Agent
    logger.info("🎙️ Starting food ordering agent session...")
    await session.start(
        agent=FoodOrderingAgent(catalog=catalog),
        room=ctx.room,
        room_input_options=RoomInputOptions(
            noise_cancellation=noise_cancellation.BVC(),
        ),
    )

    logger.info("🔗 Connecting to room...")
    await ctx.connect()
    logger.info(f"✅ Food Ordering Agent for {catalog.store_name} connected successfully!")

if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint, prewarm_fnc=prewarm))
