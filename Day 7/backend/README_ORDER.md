# Food & Grocery Order Agent (Day 7)

This agent implements a small shopping assistant that lets users:
- Browse and add items from a catalog
- Add ingredients for simple recipes (like a peanut butter sandwich)
- Manage a cart (add/remove/update/list)
- Place orders (saved to JSON files in `orders/`)

How to run locally (no LiveKit required)

1. Install dependencies if needed (backend):

```powershell
cd backend
uv sync
```

2. Run the lightweight interactive simulator:

```powershell
cd backend
.\.venv\Scripts\python.exe sim_local_order.py
```

3. Run the programmatic simulator (adds items and places order automatically):

```powershell
cd backend
.\.venv\Scripts\python.exe run_order_simulator.py
```

Files included:
- `catalog.json` - product catalog
- `orders/` - saved orders (files are created when placing orders)
- `src/order_agent.py` - the LiveKit agent that can be used with the frontend
- `sim_local_order.py` - interactive simulator
- `run_order_simulator.py` - programmatic simulator

How the agent works (overview):
- `add_item` - add a specific item with optional quantity
- `ingredients_for` - adds multiple items mapped from `RECIPES`
- `list_cart` - lists current cart details and total
- `place_order` - writes the order as a JSON file and resets the cart
