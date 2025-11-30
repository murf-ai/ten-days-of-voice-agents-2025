#!/usr/bin/env python3
"""
Day 9 - E-commerce Voice Shopping Agent
ACP-inspired voice-driven shopping assistant
"""

import logging
import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

# Load environment variables FIRST
SCRIPT_DIR = Path(__file__).parent.parent
# Try .env first, then .env.local
env_path = SCRIPT_DIR / ".env"
if not env_path.exists():
    env_path = SCRIPT_DIR / ".env.local"
load_dotenv(env_path)

# Verify environment variables
livekit_url = os.getenv("LIVEKIT_URL")
if not livekit_url:
    raise RuntimeError(f"LIVEKIT_URL not found! Tried loading from: {env_path.absolute()}")
print(f"[OK] Loaded LIVEKIT_URL: {livekit_url}")

from livekit.agents import (
    Agent,
    AgentSession,
    JobContext,
    JobProcess,
    MetricsCollectedEvent,
    RoomInputOptions,
    RunContext,
    WorkerOptions,
    cli,
    function_tool,
    metrics,
    tokenize,
)
from livekit.plugins import (
    murf,
    silero,
    google,
    deepgram,
    noise_cancellation,
)
from livekit.plugins.turn_detector.multilingual import MultilingualModel

# Import merchant functions
try:
    from merchant import list_products, create_order, get_last_order
    print("[OK] Successfully imported merchant functions")
except ImportError as e:
    print(f"[ERROR] Failed to import merchant: {e}")
    raise

# Import catalog for verification
try:
    from catalog import PRODUCTS
    print(f"[OK] Successfully imported catalog with {len(PRODUCTS)} products")
except ImportError as e:
    print(f"[ERROR] Failed to import catalog: {e}")
    raise

logger = logging.getLogger("shopping-agent")
logger.setLevel(logging.INFO)


class ShoppingAgent(Agent):
    """E-commerce Voice Shopping Agent - ACP-inspired"""

    def __init__(self) -> None:
        super().__init__(
            instructions=(
                "You are a shopping assistant. You MUST use the browse_catalog function for ANY product question.\n"
                "\n"
                "MANDATORY RULES:\n"
                "1. Customer asks about products → IMMEDIATELY call browse_catalog()\n"
                "2. Customer wants to buy → call place_order() with product_id\n"
                "3. Customer asks about order → call view_last_order()\n"
                "\n"
                "DO NOT answer product questions without calling browse_catalog first!\n"
                "\n"
                "CATEGORIES: mug, tshirt, hoodie, cap, bag\n"
                "COLORS: white, black, blue, grey, navy blue, beige\n"
                "\n"
                "FUNCTION CALL EXAMPLES:\n"
                "User: 'show me mugs' → YOU: call browse_catalog(category='mug', max_price=0, color='')\n"
                "User: 'what do you have' → YOU: call browse_catalog(category='', max_price=0, color='')\n"
                "User: 'hoodies under 1600' → YOU: call browse_catalog(category='hoodie', max_price=1600, color='')\n"
                "User: 'black items' → YOU: call browse_catalog(category='', max_price=0, color='black')\n"
                "User: 'I want the first one in size M' → YOU: call place_order(product_id='...', size='M')\n"
                "\n"
                "IMPORTANT: ALWAYS provide ALL THREE parameters (category, max_price, color) when calling browse_catalog.\n"
                "Use empty string '' for category/color and 0 for max_price when not filtering.\n"
                "\n"
                "After calling browse_catalog, read the results naturally. Don't read IDs aloud.\n"
                "For clothing orders, ask for size (S/M/L/XL) before calling place_order.\n"
                "All prices are in ₹ (Indian Rupees).\n"
            ),
        )
        self.room = None
        self.last_shown_products = []  # Track products shown to user
        self.customer_name = None
    
    async def on_enter(self):
        """Greet the customer when they connect"""
        await self.session.say(
            "Welcome! I can help you browse our products. "
            "We have mugs, t-shirts, hoodies, caps, and bags. "
            "What would you like to see?"
        )
    
    @function_tool
    async def browse_catalog(
        self,
        category: str,
        max_price: int,
        color: str,
    ) -> str:
        """
        Search and display products from the catalog. Call this for ANY product inquiry.

        Args:
            category: Filter by category - use 'mug', 'tshirt', 'hoodie', 'cap', or 'bag'. Use empty string '' to show all.
            max_price: Filter by maximum price in Indian Rupees (e.g., 1000 for items under ₹1000). Use 0 for no limit.
            color: Filter by color - use 'white', 'black', 'blue', 'grey', 'navy blue', or 'beige'. Use empty string '' for all colors.

        Returns:
            Formatted list of matching products with names, prices, and IDs

        Examples:
            - browse_catalog(category='', max_price=0, color='') - show all products
            - browse_catalog(category='mug', max_price=0, color='') - show all mugs
            - browse_catalog(category='hoodie', max_price=1600, color='') - show hoodies under ₹1600
            - browse_catalog(category='', max_price=0, color='black') - show all black items
        """
        logger.info(f"browse_catalog called with category={category}, max_price={max_price}, color={color}")

        # Convert empty strings and 0 to None for the merchant layer
        cat = category if category else None
        price = max_price if max_price > 0 else None
        col = color if color else None

        try:
            products = list_products(category=cat, max_price=price, color=col)

            logger.info(f"Found {len(products)} products")

            # Store for context
            self.last_shown_products = products

            if not products:
                return "I couldn't find any products matching those criteria. Would you like to try different filters?"

            # Format response - include product IDs for ordering
            result = f"I found {len(products)} product(s):\n\n"
            for i, product in enumerate(products[:5], 1):  # Show max 5
                result += f"{i}. {product['name']} - ₹{product['price']}"
                if "color" in product.get("attributes", {}):
                    result += f" ({product['attributes']['color']})"
                result += f" [ID: {product['id']}]"  # Include ID for ordering
                result += "\n"

            if len(products) > 5:
                result += f"\n...and {len(products) - 5} more items."

            logger.info(f"Returning result with {len(products)} products")
            return result

        except Exception as e:
            logger.error(f"ERROR in browse_catalog: {type(e).__name__}: {e}", exc_info=True)
            return f"Sorry, I encountered an error: {str(e)}"

    @function_tool
    async def place_order(
        self,
        context: RunContext,
        product_id: str,
        quantity: int = 1,
        size: Optional[str] = None,
        customer_name: Optional[str] = None,
    ) -> str:
        """
        Place an order for a product.

        Args:
            product_id: Product ID (e.g., "mug-001", "tshirt-002", "hoodie-001")
            quantity: Number of items to order (default: 1)
            size: Size for clothing items (S, M, L, XL)
            customer_name: Customer's name

        Returns:
            Order confirmation details
        """
        logger.info(f"place_order called with product_id={product_id}, quantity={quantity}, size={size}, customer_name={customer_name}")

        try:
            # Store customer name
            if customer_name:
                self.customer_name = customer_name

            # Create line items
            line_items = [{
                "product_id": product_id,
                "quantity": quantity,
            }]

            if size:
                line_items[0]["size"] = size

            logger.info(f"Creating order with line_items={line_items}")

            # Create order
            order = create_order(line_items, customer_name=self.customer_name)

            logger.info(f"Order created successfully: {order['id']}")

            # Format confirmation
            result = f"Order confirmed! Order ID: {order['id']}\n\n"
            result += "Items:\n"
            for item in order["items"]:
                result += f"- {item['product_name']} x{item['quantity']}"
                if "size" in item:
                    result += f" (Size: {item['size']})"
                result += f" - ₹{item['item_total']}\n"

            result += f"\nTotal: ₹{order['total']}\n"
            result += f"Status: {order['status']}"

            return result

        except ValueError as e:
            return f"Sorry, I couldn't place that order: {str(e)}"
        except Exception as e:
            logger.error(f"Error placing order: {e}")
            return "Sorry, there was an error placing your order. Please try again."

    @function_tool
    async def view_last_order(self, context: RunContext) -> str:
        """
        View the most recent order details.

        Returns:
            Details of the last order placed
        """
        order = get_last_order()

        if not order:
            return "You haven't placed any orders yet. Would you like to browse our products?"

        # Format order details
        result = f"Your last order (ID: {order['id']}):\n\n"
        result += "Items:\n"
        for item in order["items"]:
            result += f"- {item['product_name']} x{item['quantity']}"
            if "size" in item:
                result += f" (Size: {item['size']})"
            result += f" - ₹{item['item_total']}\n"

        result += f"\nTotal: ₹{order['total']}\n"
        result += f"Status: {order['status']}\n"
        result += f"Ordered at: {order['created_at']}"

        return result


def prewarm(proc: JobProcess):
    """Prewarm function to load VAD model"""
    proc.userdata['vad'] = silero.VAD.load()


async def entrypoint(ctx: JobContext):
    """Main entrypoint for the shopping agent"""
    ctx.log_context_fields = {'room': ctx.room.name}

    session = AgentSession(
        stt=deepgram.STT(model='nova-3'),
        llm=google.LLM(model='gemini-2.5-flash'),
        tts=murf.TTS(
            voice='en-US-matthew',
            style='Conversation',
            tokenizer=tokenize.basic.SentenceTokenizer(min_sentence_len=2),
            text_pacing=True,
        ),
        turn_detection=MultilingualModel(),
        vad=ctx.proc.userdata['vad'],
        preemptive_generation=True,
    )

    usage_collector = metrics.UsageCollector()

    @session.on('metrics_collected')
    def _on_metrics_collected(ev: MetricsCollectedEvent):
        metrics.log_metrics(ev.metrics)
        usage_collector.collect(ev.metrics)

    async def log_usage():
        summary = usage_collector.get_summary()
        logger.info(f"Usage: {summary}")

    ctx.add_shutdown_callback(log_usage)

    agent = ShoppingAgent()
    agent.room = ctx.room

    await session.start(agent=agent, room=ctx.room, room_input_options=RoomInputOptions(noise_cancellation=noise_cancellation.BVC()))
    await ctx.connect()


if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint, prewarm_fnc=prewarm))

