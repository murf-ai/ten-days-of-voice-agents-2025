import json
import logging
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

from livekit.agents import (
    Agent,
    AgentSession,
    JobContext,
    JobProcess,
    WorkerOptions,
    RoomInputOptions,
    cli,
)

from livekit.plugins import (
    deepgram,
    google,
    murf,
    noise_cancellation,
    silero,
)
from livekit.plugins.turn_detector.multilingual import MultilingualModel

logger = logging.getLogger("ecommerce_agent")
load_dotenv(".env.local")

# =====================================================
# FILES & DATA
# =====================================================
DATA_DIR = Path("shared-data")
DATA_DIR.mkdir(exist_ok=True)

CATALOG_PATH = DATA_DIR / "catalog.json"
ORDERS_PATH = DATA_DIR / "orders.json"

SAMPLE_CATALOG = [
    {"id": "mug-001", "name": "Stoneware Coffee Mug", "price": 800, "currency": "INR", "category": "mug", "color": "white"},
    {"id": "shirt-001", "name": "Black Hoodie", "price": 1200, "currency": "INR", "category": "clothing", "color": "black", "size": ["S","M","L"]},
    {"id": "shirt-002", "name": "White T-Shirt", "price": 700, "currency": "INR", "category": "clothing", "color": "white", "size": ["M","L"]},
    {"id": "mug-002", "name": "Blue Ceramic Mug", "price": 850, "currency": "INR", "category": "mug", "color": "blue"},
]

if not CATALOG_PATH.exists():
    json.dump(SAMPLE_CATALOG, open(CATALOG_PATH, "w"), indent=2)

if not ORDERS_PATH.exists():
    json.dump([], open(ORDERS_PATH, "w"), indent=2)

# =====================================================
# COMMERCE FUNCTIONS (ACP-inspired)
# =====================================================
def list_products(filters=None):
    products = json.load(open(CATALOG_PATH, "r"))
    if not filters:
        return products
    results = []
    for p in products:
        match = True
        for k,v in filters.items():
            if k not in p:
                match = False
                break
            if isinstance(v, list):
                if not any(i.lower() == p[k].lower() for i in v):
                    match = False
            else:
                if str(v).lower() != str(p[k]).lower():
                    match = False
        if match:
            results.append(p)
    return results

def create_order(line_items):
    products = json.load(open(CATALOG_PATH, "r"))
    order_items = []
    total = 0
    for item in line_items:
        prod = next((p for p in products if p["id"] == item["product_id"]), None)
        if prod:
            qty = item.get("quantity",1)
            order_items.append({
                "product_id": prod["id"],
                "name": prod["name"],
                "quantity": qty,
                "price": prod["price"],
                "currency": prod["currency"]
            })
            total += prod["price"] * qty
    order = {
        "id": f"ORD-{int(datetime.now().timestamp())}",
        "items": order_items,
        "total": total,
        "currency": "INR",
        "created_at": datetime.now().isoformat()
    }
    all_orders = json.load(open(ORDERS_PATH, "r"))
    all_orders.append(order)
    json.dump(all_orders, open(ORDERS_PATH, "w"), indent=2)
    return order

def get_last_order():
    orders = json.load(open(ORDERS_PATH, "r"))
    return orders[-1] if orders else None

# =====================================================
# SYSTEM PROMPT
# =====================================================
SHOP_SYSTEM_PROMPT = """
You are a friendly e-commerce voice assistant.

RULES:
- Understand what user wants to buy.
- List products by category, color, size, or price range.
- Allow the user to place orders.
- Confirm orders with total price and items.
- Summarize last order if asked.
- Always respond conversationally.
"""

# =====================================================
# E-COMMERCE VOICE AGENT
# =====================================================
class EcommerceAgent(Agent):

    def __init__(self):
        super().__init__(instructions=SHOP_SYSTEM_PROMPT)
        self.sessions = {}

    async def on_join(self, ctx):
        sid = ctx.session.session_id
        self.sessions[sid] = {"cart": []}
        await ctx.send_speech("Welcome! I can help you browse products and place orders. What are you looking for today?")

    async def on_user_message(self, message, ctx):
        text = (message.text or "").strip().lower()
        sid = ctx.session.session_id
        state = self.sessions[sid]

        # LAST ORDER
        if "last order" in text or "what did i buy" in text:
            last = get_last_order()
            if last:
                msg = f"Your last order ({last['id']}) had "
                for item in last["items"]:
                    msg += f"{item['quantity']} {item['name']}, "
                msg += f"totaling {last['total']} {last['currency']}."
                return await ctx.send_speech(msg)
            return await ctx.send_speech("You have no previous orders.")

        # PLACE ORDER
        if "buy" in text or "order" in text:
            # let LLM interpret cart items
            response = await ctx.session.llm.generate(messages=[
                {"role": "system", "content": SHOP_SYSTEM_PROMPT},
                {"role": "user", "content": f"User said: '{text}'. Output a JSON array of items: {{'product_id', 'quantity'}}"}
            ])
            try:
                line_items = json.loads(response.text)
            except:
                return await ctx.send_speech("Sorry, I couldn't understand which product you want to buy.")
            order = create_order(line_items)
            return await ctx.send_speech(f"Order placed! {len(order['items'])} items totaling {order['total']} INR.")

        # BROWSE PRODUCTS
        response = await ctx.session.llm.generate(messages=[
            {"role": "system", "content": SHOP_SYSTEM_PROMPT},
            {"role": "user", "content": f"User said: '{text}'. Output filters as JSON dictionary (category, color, max_price, etc)."}
        ])
        try:
            filters = json.loads(response.text)
        except:
            filters = None
        products = list_products(filters)
        if not products:
            return await ctx.send_speech("No products found matching your request.")
        msg = "I found the following products:\n"
        for i,p in enumerate(products[:5],1):
            msg += f"{i}. {p['name']} - {p['price']} {p['currency']}\n"
        await ctx.send_speech(msg + "Would you like to buy any of these?")

# =====================================================
# PREWARM VAD
# =====================================================
vad_model = silero.VAD.load()
def prewarm(proc: JobProcess):
    proc.userdata["vad"] = vad_model

# =====================================================
# ENTRYPOINT
# =====================================================
async def entrypoint(ctx: JobContext):
    session = AgentSession(
        stt=deepgram.STT(model="nova-3"),
        llm=google.LLM(model="gemini-2.5-flash"),
        tts=murf.TTS(voice="en-US-matthew", style="Conversation"),
        turn_detection=MultilingualModel(),
        vad=ctx.proc.userdata["vad"],
        preemptive_generation=True,
    )
    await session.start(
        agent=EcommerceAgent(),
        room=ctx.room,
        room_input_options=RoomInputOptions(noise_cancellation=noise_cancellation.BVC())
    )
    await ctx.connect()

if __name__ == "__main__":
    cli.run_app(
        WorkerOptions(entrypoint_fnc=entrypoint, prewarm_fnc=prewarm)
    )
