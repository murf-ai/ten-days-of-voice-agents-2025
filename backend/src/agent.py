import logging
import json
from pathlib import Path
from datetime import datetime
from typing import Annotated

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
logger.setLevel(logging.INFO)

load_dotenv(".env.local")

# Product catalog (ACP-inspired structure)
PRODUCTS = [
    {
        "id": "mug-001",
        "name": "Classic White Coffee Mug",
        "description": "Elegant stoneware coffee mug, 350ml capacity",
        "price": 450,
        "currency": "INR",
        "category": "mug",
        "color": "white",
        "material": "stoneware"
    },
    {
        "id": "mug-002",
        "name": "Blue Ceramic Mug",
        "description": "Handcrafted ceramic mug with ocean blue glaze",
        "price": 550,
        "currency": "INR",
        "category": "mug",
        "color": "blue",
        "material": "ceramic"
    },
    {
        "id": "tshirt-001",
        "name": "Cotton T-Shirt Black",
        "description": "Premium cotton t-shirt, comfortable fit",
        "price": 799,
        "currency": "INR",
        "category": "tshirt",
        "color": "black",
        "sizes": ["S", "M", "L", "XL"]
    },
    {
        "id": "tshirt-002",
        "name": "Cotton T-Shirt White",
        "description": "Premium cotton t-shirt, comfortable fit",
        "price": 699,
        "currency": "INR",
        "category": "tshirt",
        "color": "white",
        "sizes": ["S", "M", "L", "XL"]
    },
    {
        "id": "hoodie-001",
        "name": "Black Hoodie Premium",
        "description": "Warm fleece hoodie with kangaroo pocket",
        "price": 1899,
        "currency": "INR",
        "category": "hoodie",
        "color": "black",
        "sizes": ["M", "L", "XL"]
    },
    {
        "id": "hoodie-002",
        "name": "Grey Hoodie Classic",
        "description": "Classic grey hoodie with soft interior",
        "price": 1699,
        "currency": "INR",
        "category": "hoodie",
        "color": "grey",
        "sizes": ["S", "M", "L", "XL"]
    },
    {
        "id": "bottle-001",
        "name": "Stainless Steel Water Bottle",
        "description": "Insulated water bottle, keeps drinks cold for 24 hours",
        "price": 899,
        "currency": "INR",
        "category": "bottle",
        "color": "silver",
        "capacity": "750ml"
    },
    {
        "id": "bag-001",
        "name": "Canvas Tote Bag",
        "description": "Durable canvas bag perfect for shopping or daily use",
        "price": 599,
        "currency": "INR",
        "category": "bag",
        "color": "beige",
        "material": "canvas"
    },
    {
        "id": "notebook-001",
        "name": "Leather Journal",
        "description": "Premium leather-bound notebook with 200 pages",
        "price": 1299,
        "currency": "INR",
        "category": "notebook",
        "color": "brown",
        "pages": 200
    },
    {
        "id": "cap-001",
        "name": "Baseball Cap Black",
        "description": "Adjustable baseball cap with embroidered logo",
        "price": 499,
        "currency": "INR",
        "category": "cap",
        "color": "black",
        "adjustable": True
    }
]

# In-memory order storage
ORDERS = []

# Orders file path
ORDERS_DIR = Path(__file__).parent.parent / "shared-data" / "orders"
ORDERS_DIR.mkdir(parents=True, exist_ok=True)
ORDERS_FILE = ORDERS_DIR / "orders.json"

# Load existing orders from file
if ORDERS_FILE.exists():
    try:
        with open(ORDERS_FILE, "r", encoding="utf-8") as f:
            ORDERS = json.load(f)
        logger.info(f"Loaded {len(ORDERS)} existing orders from {ORDERS_FILE}")
    except Exception as e:
        logger.error(f"Error loading orders: {e}")
        ORDERS = []


# Function tools - all parameters are REQUIRED (no defaults)
# We handle empty values inside the function
@function_tool()
async def list_products(
    context: RunContext,
    category: Annotated[str, "Product category: mug, tshirt, hoodie, bottle, bag, notebook, cap, or 'all' for everything"],
    max_price: Annotated[int, "Maximum price in INR, or 0 for no limit"],
    color: Annotated[str, "Color filter: white, blue, black, grey, silver, beige, brown, or 'all' for any color"],
) -> str:
    """
    Browse the product catalog with filters.
    Use 'all' for category or color to show everything.
    Use 0 for max_price to show all prices.
    """
    
    logger.info(f"=== list_products called ===")
    logger.info(f"Parameters: category='{category}', max_price={max_price}, color='{color}'")
    
    try:
        filtered = list(PRODUCTS)
        
        # Apply filters - treat "all" or empty as no filter
        if category and category.lower().strip() not in ["all", ""]:
            cat_lower = category.lower().strip()
            filtered = [p for p in filtered if p.get("category", "").lower() == cat_lower]
            logger.info(f"After category filter '{cat_lower}': {len(filtered)} products")
        
        if max_price and max_price > 0:
            filtered = [p for p in filtered if p.get("price", 0) <= max_price]
            logger.info(f"After price filter <={max_price}: {len(filtered)} products")
        
        if color and color.lower().strip() not in ["all", ""]:
            col_lower = color.lower().strip()
            filtered = [p for p in filtered if p.get("color", "").lower() == col_lower]
            logger.info(f"After color filter '{col_lower}': {len(filtered)} products")
        
        if not filtered:
            return "No products found matching your criteria. Try different filters."
        
        # Format response
        result = f"I found {len(filtered)} product(s):\n\n"
        for i, product in enumerate(filtered, 1):
            result += f"{i}. {product['name']} (ID: {product['id']})\n"
            result += f"   Price: ₹{product['price']}\n"
            result += f"   Color: {product.get('color', 'N/A')}\n"
            if 'sizes' in product:
                result += f"   Sizes: {', '.join(product['sizes'])}\n"
            result += f"   {product['description']}\n\n"
        
        logger.info(f"Returning {len(filtered)} products successfully")
        return result.strip()
        
    except Exception as e:
        logger.error(f"ERROR in list_products: {str(e)}", exc_info=True)
        return f"Error browsing products: {str(e)}"


@function_tool()
async def create_order(
    context: RunContext,
    product_id: Annotated[str, "Product ID (e.g., hoodie-001, mug-002)"],
    size: Annotated[str, "Size for clothing (S, M, L, XL), or 'none' for non-clothing items"],
    quantity: Annotated[int, "Quantity to order"],
    customer_name: Annotated[str, "Customer's name"],
) -> str:
    """
    Create an order for a product.
    For clothing (hoodies, tshirts), size is required (S, M, L, XL).
    For other items, use 'none' for size.
    """
    
    logger.info(f"=== create_order called ===")
    logger.info(f"Parameters: product_id='{product_id}', size='{size}', quantity={quantity}, customer_name='{customer_name}'")
    
    try:
        # Find product
        product = None
        for p in PRODUCTS:
            if p["id"].lower() == product_id.lower().strip():
                product = p
                break
        
        if not product:
            logger.error(f"Product not found: {product_id}")
            return f"Product ID '{product_id}' not found. Please browse the catalog first with list_products."
        
        # Validate size for clothing
        actual_size = None
        if 'sizes' in product:
            if not size or size.lower() == "none":
                return f"Size is required for {product['name']}. Available sizes: {', '.join(product['sizes'])}"
            
            size_upper = size.upper().strip()
            if size_upper not in product['sizes']:
                return f"Size {size} is not available. Available sizes: {', '.join(product['sizes'])}"
            actual_size = size_upper
        
        # Calculate total
        unit_price = product["price"]
        total = unit_price * quantity
        
        # Generate order ID
        order_id = f"ORD{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        # Create order object
        order = {
            "id": order_id,
            "status": "CONFIRMED",
            "created_at": datetime.now().isoformat(),
            "customer_name": customer_name,
            "line_items": [
                {
                    "product_id": product["id"],
                    "product_name": product["name"],
                    "quantity": quantity,
                    "unit_amount": unit_price,
                    "size": actual_size,
                    "subtotal": total
                }
            ],
            "total": total,
            "currency": product["currency"]
        }
        
        # Save to memory
        ORDERS.append(order)
        
        # Save to file
        try:
            with open(ORDERS_FILE, "w", encoding="utf-8") as f:
                json.dump(ORDERS, f, indent=2, ensure_ascii=False)
            logger.info(f"Order {order_id} saved to {ORDERS_FILE}")
        except Exception as e:
            logger.error(f"Error saving order: {e}")
        
        # Format confirmation
        confirmation = f"Order confirmed!\n\n"
        confirmation += f"Order ID: {order_id}\n"
        confirmation += f"Customer: {customer_name}\n"
        confirmation += f"Product: {product['name']}\n"
        confirmation += f"Quantity: {quantity}\n"
        if actual_size:
            confirmation += f"Size: {actual_size}\n"
        confirmation += f"Total: ₹{total}\n"
        confirmation += f"\nYour order will be processed shortly. Thank you for shopping with us!"
        
        logger.info(f"Order {order_id} created successfully")
        return confirmation
        
    except Exception as e:
        logger.error(f"ERROR in create_order: {str(e)}", exc_info=True)
        return f"Error creating order: {str(e)}"


@function_tool()
async def view_last_order(context: RunContext) -> str:
    """View the most recent order details"""
    
    logger.info(f"=== view_last_order called ===")
    
    try:
        if not ORDERS:
            return "You haven't placed any orders yet. Would you like to browse our products?"
        
        order = ORDERS[-1]
        
        result = f"Last Order:\n\n"
        result += f"Order ID: {order['id']}\n"
        result += f"Status: {order['status']}\n"
        result += f"Customer: {order['customer_name']}\n\n"
        result += "Items:\n"
        
        for item in order['line_items']:
            result += f"- {item['product_name']}\n"
            result += f"  Quantity: {item['quantity']}\n"
            if item.get('size'):
                result += f"  Size: {item['size']}\n"
            result += f"  Price: ₹{item['subtotal']}\n"
        
        result += f"\nTotal: ₹{order['total']} {order['currency']}"
        
        logger.info("Last order retrieved successfully")
        return result
        
    except Exception as e:
        logger.error(f"ERROR in view_last_order: {str(e)}", exc_info=True)
        return f"Error viewing order: {str(e)}"


# E-commerce Agent class
class EcommerceAgent(Agent):
    """Voice Shopping Assistant"""
    
    def __init__(self) -> None:
        super().__init__(
            instructions="""You are a helpful voice shopping assistant.

YOUR TOOLS:
1. list_products(category, max_price, color) - Browse catalog
2. create_order(product_id, size, quantity, customer_name) - Place order
3. view_last_order() - Show recent order

IMPORTANT RULES FOR CALLING TOOLS:

list_products:
- ALWAYS provide ALL THREE parameters
- Use "all" for category if showing everything (not a specific category)
- Use 0 for max_price if no price limit
- Use "all" for color if showing all colors

Examples:
- All products: list_products("all", 0, "all")
- Hoodies only: list_products("hoodie", 0, "all")
- Blue items: list_products("all", 0, "blue")
- Hoodies under 2000: list_products("hoodie", 2000, "all")

create_order:
- ALWAYS provide ALL FOUR parameters
- For hoodies/tshirts: ask for size first (S, M, L, XL)
- For other items: use "none" for size
- Always ask for customer name

Examples:
- Hoodie: create_order("hoodie-001", "L", 1, "John")
- Mug: create_order("mug-001", "none", 1, "Jane")

WORKFLOW:
1. Customer asks about products → call list_products
2. Customer wants to order → get product_id, size (if clothing), name → call create_order
3. Customer asks about last order → call view_last_order

Keep responses SHORT and friendly (1-2 sentences).

Greet the customer and ask how you can help!""",
            tools=[list_products, create_order, view_last_order]
        )


def prewarm(proc: JobProcess):
    """Prewarm process with VAD model"""
    proc.userdata["vad"] = silero.VAD.load()


async def entrypoint(ctx: JobContext):
    """Main agent entrypoint"""
    
    logger.info("=" * 50)
    logger.info("Starting E-commerce Agent")
    logger.info("=" * 50)
    
    # Create agent session
    session = AgentSession(
        stt=deepgram.STT(model="nova-3"),
        llm=google.LLM(model="gemini-2.0-flash-lite"),
        tts=murf.TTS(
            voice="en-IN-priya", 
            style="Conversation",
            tokenizer=tokenize.basic.SentenceTokenizer(min_sentence_len=8)
        ),
        turn_detection=MultilingualModel(),
        vad=ctx.proc.userdata["vad"],
        preemptive_generation=True,
    )
    
    # Metrics
    usage_collector = metrics.UsageCollector()
    
    @session.on("user_speech_committed")
    def on_user_speech(msg):
        logger.info(f"USER SAID: {msg.text}")
    
    @session.on("agent_speech_committed")
    def on_agent_speech(msg):
        logger.info(f"AGENT SAID: {msg.text}")
    
    @session.on("function_calls_collected")
    def on_function_calls(calls):
        logger.info(f"FUNCTION CALLS: {[call.function_info.name for call in calls.function_calls]}")
    
    @session.on("metrics_collected")
    def _on_metrics_collected(ev: MetricsCollectedEvent):
        metrics.log_metrics(ev.metrics)
        usage_collector.collect(ev.metrics)
    
    async def log_usage():
        summary = usage_collector.get_summary()
        logger.info(f"Session Usage Summary: {summary}")
    
    ctx.add_shutdown_callback(log_usage)
    
    # Start agent
    await session.start(
        agent=EcommerceAgent(),
        room=ctx.room,
        room_input_options=RoomInputOptions(
            noise_cancellation=noise_cancellation.BVC(),
        ),
    )
    
    await ctx.connect()
    
    logger.info("Agent connected and ready!")


if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint, prewarm_fnc=prewarm))