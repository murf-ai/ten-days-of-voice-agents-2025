import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
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

logger = logging.getLogger("order_agent")

load_dotenv(".env.local")

CATALOG_PATH = Path("catalog.json")
ORDERS_DIR = Path("orders")
ORDERS_DIR.mkdir(exist_ok=True)

# Simple recipes map dish name -> list of item ids
RECIPES = {
    "peanut butter sandwich": ["bread_whole_wheat", "peanut_butter"],
    "pasta for two": ["pasta_spaghetti", "pasta_sauce", "olive_oil"],
    "omelette": ["eggs_large", "milk_2l", "cheddar_cheese"],
}


def load_catalog() -> list:
    if not CATALOG_PATH.exists():
        return []
    with open(CATALOG_PATH, "r") as f:
        return json.load(f)


def find_item_by_name(name: str, catalog: list) -> Optional[dict]:
    name = name.lower()
    for item in catalog:
        if name == item["id"].lower() or name == item["name"].lower() or name in item["name"].lower():
            return item
    return None


class OrderAgent(Agent):
    def __init__(self) -> None:
        super().__init__(
            instructions=(
                "You are a friendly food & grocery ordering assistant. You can help users order items, manage a cart, and place orders. "
                "Ask clarifying questions for quantities or sizes and confirm before placing the order."
            )
        )
        self.room = None
        self.catalog = load_catalog()
        self.cart: dict[str, dict] = {}

    @function_tool
    async def greet(self, context: RunContext) -> str:
        return "Hello! I can help you order groceries and prepared food. What would you like to buy today?"

    @function_tool
    async def add_item(self, context: RunContext, item_name: str, quantity: int = 1) -> str:
        item = find_item_by_name(item_name, self.catalog)
        if not item:
            return f"I couldn't find {item_name} in the catalog. Can you try another name?"
        key = item["id"]
        current = self.cart.get(key, {"item": item, "quantity": 0})
        current["quantity"] += max(1, quantity)
        self.cart[key] = current
        return f"Added {current['quantity']} x {item['name']} to your cart."

    @function_tool
    async def remove_item(self, context: RunContext, item_name: str) -> str:
        item = find_item_by_name(item_name, self.catalog)
        if not item:
            return f"I couldn't find {item_name}."
        key = item["id"]
        if key in self.cart:
            del self.cart[key]
            return f"Removed {item['name']} from the cart."
        return f"{item['name']} wasn't in your cart."

    @function_tool
    async def update_quantity(self, context: RunContext, item_name: str, quantity: int) -> str:
        item = find_item_by_name(item_name, self.catalog)
        if not item:
            return f"I couldn't find {item_name}."
        key = item["id"]
        if key not in self.cart:
            return f"{item['name']} is not in your cart."
        if quantity <= 0:
            del self.cart[key]
            return f"Removed {item['name']} from your cart because the quantity was set to 0."
        self.cart[key]["quantity"] = quantity
        return f"Updated {item['name']} quantity to {quantity}."

    @function_tool
    async def list_cart(self, context: RunContext) -> str:
        if not self.cart:
            return "Your cart is empty."
        parts = []
        total = 0.0
        for key, val in self.cart.items():
            name = val['item']['name']
            qty = val['quantity']
            price = val['item']['price']
            parts.append(f"{qty} x {name} (${price:.2f})")
            total += qty * price
        return f"Your cart contains: {', '.join(parts)}. Total: ${total:.2f}."

    @function_tool
    async def ingredients_for(self, context: RunContext, dish: str, servings: int = 1) -> str:
        dish = dish.lower()
        if dish not in RECIPES:
            return f"I don't have a recipe for {dish}. Can I add individual items instead?"
        for item_id in RECIPES[dish]:
            item = next((i for i in self.catalog if i['id'] == item_id), None)
            if item:
                key = item_id
                self.cart.setdefault(key, {'item': item, 'quantity': 0})
                self.cart[key]['quantity'] += servings
        added = [next((i for i in self.catalog if i['id'] == id),'').get('name') if isinstance(next((i for i in self.catalog if i['id'] == id),''), dict) else id for id in RECIPES[dish]]
        return f"I've added ingredients for {dish}: {', '.join(added)} to your cart."

    @function_tool
    async def place_order(self, context: RunContext, customer_name: Optional[str] = None, address: Optional[str] = None) -> str:
        if not self.cart:
            return "Your cart is empty. I can't place an empty order."
        items = []
        total = 0.0
        for key, val in self.cart.items():
            qty = val['quantity']
            price = val['item']['price']
            total += qty * price
            items.append({
                'id': key,
                'name': val['item']['name'],
                'quantity': qty,
                'unit_price': price,
                'line_total': round(qty * price, 2),
            })
        order = {
            'customer_name': customer_name or 'Guest',
            'address': address or '',
            'items': items,
            'total': round(total, 2),
            'timestamp': datetime.now().isoformat(),
            'status': 'placed',
        }
        filename = ORDERS_DIR / f"order_{order['customer_name'].replace(' ', '_')}_{datetime.now().strftime('%Y%m%d%H%M%S')}.json"
        with open(filename, 'w') as f:
            json.dump(order, f, indent=2)
        # Reset cart
        self.cart = {}
        return f"Order placed for {order['customer_name']}. Total: ${order['total']:.2f}. Your order id is {filename.name}."


def prewarm(proc: JobProcess):
    proc.userdata['vad'] = silero.VAD.load()


async def entrypoint(ctx: JobContext):
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

    agent = OrderAgent()
    agent.room = ctx.room

    await session.start(agent=agent, room=ctx.room, room_input_options=RoomInputOptions(noise_cancellation=noise_cancellation.BVC()))

    await ctx.connect()


if __name__ == '__main__':
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint, prewarm_fnc=prewarm))
