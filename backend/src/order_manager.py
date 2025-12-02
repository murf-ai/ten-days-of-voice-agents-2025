import json
import os
from datetime import datetime

class OrderManager:
    def __init__(self):
        self.order = {
            "drinkType": "",
            "size": "",
            "milk": "",
            "extras": [],
            "name": ""
        }

    def update(self, text):
        t = text.lower()

        # drink type
        for d in ["latte", "cappuccino", "americano", "espresso", "mocha"]:
            if d in t:
                self.order["drinkType"] = d

        # size
        for s in ["small", "medium", "large"]:
            if s in t:
                self.order["size"] = s

        # milk
        for m in ["whole", "skim", "oat", "soy", "almond"]:
            if m in t:
                self.order["milk"] = m

        # extras
        for e in ["vanilla", "caramel", "hazelnut", "whipped"]:
            if e in t and e not in self.order["extras"]:
                self.order["extras"].append(e)

        # name
        if "my name is" in t:
            self.order["name"] = t.split("my name is")[-1].strip().split()[0]
        if "for" in t:
            self.order["name"] = t.split("for")[-1].strip().split()[0]

    def is_complete(self):
        return (
            self.order["drinkType"]
            and self.order["size"]
            and self.order["milk"]
            and self.order["name"]
        )

    def next_question(self):
        if not self.order["drinkType"]:
            return "What drink would you like?"
        if not self.order["size"]:
            return "What size do you prefer?"
        if not self.order["milk"]:
            return "What milk would you like?"
        if len(self.order["extras"]) == 0:
            return "Any extras like caramel or whipped cream?"
        if not self.order["name"]:
            return "What name should I put on your order?"
        return None

    def save(self):
        os.makedirs("orders", exist_ok=True)
        filename = f"orders/order_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(filename, "w") as f:
            json.dump(self.order, f, indent=2)
        return filename
