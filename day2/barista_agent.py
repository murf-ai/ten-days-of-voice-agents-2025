import os
import json
import datetime

# This folder will store order summaries
ORDERS_DIR = "orders"
os.makedirs(ORDERS_DIR, exist_ok=True)

# Initial empty order structure
DEFAULT_ORDER = {
    "drinkType": "",
    "size": "",
    "milk": "",
    "extras": [],
    "name": ""
}

ALLOWED_SIZES = {"small", "medium", "large"}
ALLOWED_MILKS = {"whole", "skim", "soy", "oat", "almond", "none"}


def normalize(text: str) -> str:
    return (text or "").strip().lower()


def parse_extras(text: str):
    text = normalize(text)
    text = text.replace(" and ", ",")
    return [x.strip() for x in text.split(",") if x.strip()]


class BaristaAgent:
    """
    This class doesn't run the whole LiveKit agent.
    You will IMPORT this inside your main agent.py and integrate it.
    """

    def __init__(self, session):
        self.session = session          # LiveKit session instance
        self.order = DEFAULT_ORDER.copy()

    async def start(self):
        """Called by your main agent file when the session begins."""
        self.order = DEFAULT_ORDER.copy()
        await self.session.say(
            "Hi! ☕ I'm your friendly coffee barista. What can I get started for you today?"
        )

    async def on_user_message(self, text: str):
        """Called every time user speaks or types something."""
        t = normalize(text)

        # ---------------------------
        # Try to fill missing fields
        # ---------------------------

        # 1) Name
        if not self.order["name"]:
            if "name is" in t or "i'm " in t or "im " in t:
                parts = text.split()
                guess = parts[-1]
                self.order["name"] = guess.capitalize()

        # 2) Size
        if not self.order["size"]:
            for s in ALLOWED_SIZES:
                if s in t:
                    self.order["size"] = s
                    break

        # 3) Drink type
        if not self.order["drinkType"]:
            drinks = [
                "latte", "cappuccino", "americano", "espresso",
                "mocha", "tea", "black coffee", "flat white"
            ]
            for d in drinks:
                if d in t:
                    self.order["drinkType"] = d
                    break

        # 4) Milk
        if not self.order["milk"]:
            for m in ALLOWED_MILKS:
                if m in t:
                    self.order["milk"] = m
                    break

        # 5) Extras
        if not self.order["extras"]:
            keywords = ["whip", "whipped", "syrup", "vanilla", "caramel", "extra shot"]
            if any(k in t for k in keywords):
                self.order["extras"] = parse_extras(t)

        # ---------------------------------
        # Ask next missing field OR finish
        # ---------------------------------
        missing = [field for field, value in self.order.items() if not value]

        if missing:
            await self.ask_for(missing[0])
        else:
            await self.complete_order()

    async def ask_for(self, field: str):
        questions = {
            "drinkType": "What drink would you like? (latte, cappuccino, americano, espresso, tea...)",
            "size": "Which size do you prefer — small, medium, or large?",
            "milk": "What kind of milk would you like? (whole, skim, oat, soy, almond, or none)",
            "extras": "Any extras? (whipped cream, caramel, vanilla, extra shot?)",
            "name": "What name should I put the order under?"
        }

        await self.session.say(questions[field])

    async def complete_order(self):
        """Save JSON and speak summary."""
        ts = datetime.datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        safe_name = (self.order["name"] or "guest").replace(" ", "_")
        filename = f"{ORDERS_DIR}/{ts}_{safe_name}.json"

        # Save order to JSON
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(self.order, f, indent=2)

        # Build summary
        extras = ", ".join(self.order["extras"]) if self.order["extras"] else "none"
        summary = (
            f"Name: {self.order['name']}\n"
            f"Drink: {self.order['drinkType']}\n"
            f"Size: {self.order['size']}\n"
            f"Milk: {self.order['milk']}\n"
            f"Extras: {extras}\n"
        )

        # Speak summary
        await self.session.say("Perfect! Your order is ready. Here’s a quick summary:")
        await self.session.say(summary)
        await self.session.say(f"I’ve saved your order to a file: {filename}")

