import asyncio
import json
from pathlib import Path
from datetime import datetime

from src.order_agent import OrderAgent, load_catalog


async def run_simulation():
    agent = OrderAgent()

    print(await agent.greet(None))

    # Add explicit item
    print("[User] Add 2 Whole Wheat Bread")
    print(await agent.add_item(None, "Whole Wheat Bread", 2))

    # Add items by 'ingredients for' mapping
    print("[User] I need ingredients for peanut butter sandwich")
    print(await agent.ingredients_for(None, "peanut butter sandwich", 1))

    # List cart
    print(await agent.list_cart(None))

    # Place order
    print(await agent.place_order(None, customer_name="John Doe", address="123 Demo St"))

    # Load last order written
    orders_dir = Path("orders")
    files = sorted(orders_dir.glob('order_*.json'))
    if not files:
        print("No orders found")
        return
    with open(files[-1], 'r') as f:
        print('\n[DB] Latest order:\n')
        print(json.dumps(json.load(f), indent=2))


if __name__ == '__main__':
    asyncio.run(run_simulation())
