# ===========================================
# Food & Grocery Ordering Voice Agent - Day 7
# ===========================================

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


logger = logging.getLogger("food_agent")
load_dotenv(".env.local")

# ------------------------------------------
# File paths
# ------------------------------------------
DATA_DIR = Path("shared-data")
DATA_DIR.mkdir(exist_ok=True)

CATALOG_PATH = DATA_DIR / "catalog.json"
ORDER_HISTORY_PATH = DATA_DIR / "orders.json"

# ------------------------------------------
# Sample Catalog
# ------------------------------------------
SAMPLE_CATALOG = {
    "items": [
        {"id": 1, "name": "Milk", "category": "Groceries", "price": 55, "size": "1L"},
        {"id": 2, "name": "Bread", "category": "Groceries", "price": 40, "type": "whole wheat"},
        {"id": 3, "name": "Eggs", "category": "Groceries", "price": 70, "units": "12 pack"},
        {"id": 4, "name": "Peanut Butter", "category": "Snacks", "price": 120},
        {"id": 5, "name": "Pasta", "category": "Groceries", "price": 85},
        {"id": 6, "name": "Pasta Sauce", "category": "Groceries", "price": 110},
        {"id": 7, "name": "Chips", "category": "Snacks", "price": 20},
        {"id": 8, "name": "Cheese Sandwich", "category": "Prepared Food", "price": 90},
        {"id": 9, "name": "Veg Pizza", "category": "Prepared Food", "price": 299},
        {"id": 10, "name": "Butter", "category": "Groceries", "price": 52}
    ]
}

# create default catalog if not exists
if not CATALOG_PATH.exists():
    json.dump(SAMPLE_CATALOG, open(CATALOG_PATH, "w"), indent=2)

# create empty order history file
if not ORDER_HISTORY_PATH.exists():
    json.dump({"orders": []}, open(ORDER_HISTORY_PATH, "w"), indent=2)


def load_catalog():
    return json.load(open(CATALOG_PATH, "r"))["items"]


def load_order_history():
    return json.load(open(ORDER_HISTORY_PATH, "r"))


def save_order(order):
    db = load_order_history()
    db["orders"].append(order)
    json.dump(db, open(ORDER_HISTORY_PATH, "w"), indent=2)


# ------------------------------------------
# Recipes for "ingredients for X"
# ------------------------------------------
RECIPES = {
    "peanut butter sandwich": ["Bread", "Peanut Butter"],
    "pasta": ["Pasta", "Pasta Sauce"],
    "sandwich": ["Bread", "Butter"],
}

# ------------------------------------------
# Food Ordering Agent
# ------------------------------------------
class FoodOrderAgent(Agent):

    def __init__(self):
        super().__init__(
            instructions=(
                "You are a friendly Food & Grocery Ordering Assistant for QuickMart. "
                "You help customers order groceries, snacks, and simple meals. "
                "You maintain a cart, add items, remove items, list cart contents, "
                "and process ingredient-based requests like 'ingredients for pasta'. "
                "When the user says 'place my order', save the order as JSON."
            )
        )
        self.sessions = {}

    async def on_join(self, ctx):
        sid = ctx.session.session_id

        self.sessions[sid] = {
            "cart": [],
            "catalog": load_catalog(),
        }

        await ctx.send_speech(
            "Welcome to QuickMart! I can help you order groceries and snacks. "
            "Tell me what you'd like to buy."
        )

    async def on_user_message(self, message, ctx):
        text = (message.text or "").lower()
        sid = ctx.session.session_id
        state = self.sessions[sid]

        # EXIT
        if text in ["bye", "exit", "stop"]:
            return await self.finish(ctx)

        # PLACE ORDER
        if "place" in text and "order" in text:
            return await self.place_order(ctx, state)

        # LIST CART
        if "what" in text and "cart" in text:
            return await self.list_cart(ctx, state)

        # REMOVE ITEM
        if "remove" in text:
            return await self.remove_item(text, ctx, state)

        # INGREDIENT request
        if "ingredients for" in text:
            return await this.ingredients_request(text, ctx, state)

        # ADD NORMAL ITEM
        return await self.add_item(text, ctx, state)

    # ---------------------- CART OPERATIONS ----------------------
    async def add_item(self, text, ctx, state):
        catalog = state["catalog"]
        quantity = 1

        # detect quantity
        for q in range(1, 6):
            if f"{q}" in text:
                quantity = q

        # find matching item
        for item in catalog:
            if item["name"].lower() in text:
                state["cart"].append({"name": item["name"], "qty": quantity, "price": item["price"]})
                return await ctx.send_speech(f"Added {quantity} {item['name']} to your cart.")

        await ctx.send_speech("I couldn't find that item in our store. Try again.")

    async def remove_item(self, text, ctx, state):
        for c in state["cart"]:
            if c["name"].lower() in text:
                state["cart"].remove(c)
                return await ctx.send_speech(f"Removed {c['name']} from your cart.")

        await ctx.send_speech("That item is not in your cart.")

    async def list_cart(self, ctx, state):
        if not state["cart"]:
            return await ctx.send_speech("Your cart is empty.")

        msg = "Your cart contains: "
        for c in state["cart"]:
            msg += f"{c['qty']} {c['name']}, "

        await ctx.send_speech(msg)

    # ---------------------- INGREDIENTS ----------------------
    async def ingredients_request(self, text, ctx, state):
        for dish in RECIPES:
            if dish in text:
                items = RECIPES[dish]
                for i in items:
                    state["cart"].append({"name": i, "qty": 1, "price": self.find_price(state, i)})
                return await ctx.send_speech(
                    f"I've added the ingredients for {dish}: {', '.join(items)}."
                )

        await ctx.send_speech("I don’t have a recipe for that, sorry!")

    def find_price(self, state, name):
        for item in state["catalog"]:
            if item["name"] == name:
                return item["price"]
        return 0

    # ---------------------- PLACE ORDER ----------------------
    async def place_order(self, ctx, state):
        if not state["cart"]:
            return await ctx.send_speech("Your cart is empty. Add items before placing an order.")

        total = sum(i["price"] * i["qty"] for i in state["cart"])
        order = {
            "timestamp": datetime.now().isoformat(),
            "items": state["cart"],
            "total": total
        }

        save_order(order)

        await ctx.send_speech(
            f"Your order has been placed! Total amount is {total} rupees. "
            "You will receive your order soon!"
        )

        state["cart"] = []

    async def finish(self, ctx):
        await ctx.send_speech("Thanks for shopping with QuickMart! Goodbye.")

# ------------------------------------------
# Prewarm VAD
# ------------------------------------------
vad_model = silero.VAD.load()

def prewarm(proc: JobProcess):
    proc.userdata["vad"] = vad_model

# ------------------------------------------
# Entrypoint
# ------------------------------------------
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
        agent=FoodOrderAgent(),
        room=ctx.room,
        room_input_options=RoomInputOptions(
            noise_cancellation=noise_cancellation.BVC()
        ),
    )
    await ctx.connect()

if __name__ == "__main__":
    cli.run_app(
        WorkerOptions(
            entrypoint_fnc=entrypoint,
            prewarm_fnc=prewarm,
        )
    )
