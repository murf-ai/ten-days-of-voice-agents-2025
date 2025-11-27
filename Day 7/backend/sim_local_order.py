import json
from pathlib import Path
from datetime import datetime

CATALOG_PATH = Path("catalog.json")
ORDERS_DIR = Path("orders")
ORDERS_DIR.mkdir(exist_ok=True)


def load_catalog():
    with open(CATALOG_PATH, 'r') as f:
        return json.load(f)


def find_item(catalog, name):
    name = name.lower()
    for item in catalog:
        if name in item['id'] or name in item['name'].lower():
            return item
    return None


if __name__ == '__main__':
    catalog = load_catalog()
    cart = {}

    print("[Agent] Hello! I'm your Grocery Assistant. What can I help you find today?")
    while True:
        msg = input('[User] ').strip()
        if not msg:
            continue
        if msg.lower().startswith('add'):
            # parse "add 2 bread" or "add bread"
            parts = msg.split()
            qty = 1
            if len(parts) >= 3 and parts[1].isdigit():
                qty = int(parts[1])
                item_name = ' '.join(parts[2:])
            else:
                item_name = ' '.join(parts[1:])
            item = find_item(catalog, item_name)
            if not item:
                print(f"[Agent] I couldn't find {item_name}.")
                continue
            key = item['id']
            cart.setdefault(key, {'item': item, 'quantity': 0})
            cart[key]['quantity'] += qty
            print(f"[Agent] Added {qty} x {item['name']} to your cart.")
            continue
        if msg.lower().startswith('ingredients for'):
            dish = msg[len('ingredients for'):].strip().lower()
            recipes = {
                'peanut butter sandwich': ['bread_whole_wheat', 'peanut_butter'],
                'pasta for two': ['pasta_spaghetti', 'pasta_sauce', 'olive_oil'],
                'omelette': ['eggs_large', 'cheddar_cheese', 'milk_2l']
            }
            if dish not in recipes:
                print(f"[Agent] Sorry, I don't have a recipe for {dish}.")
                continue
            for iid in recipes[dish]:
                it = next((x for x in catalog if x['id'] == iid), None)
                if it:
                    cart.setdefault(iid, {'item': it, 'quantity': 0})
                    cart[iid]['quantity'] += 1
            added = ', '.join([x['item']['name'] for x in cart.values() if x['item']['id'] in recipes[dish]])
            print(f"[Agent] I've added ingredients for {dish}: {added} to your cart.")
            continue
        if msg.lower() in ('cart', 'what is in my cart', "what's in my cart"):
            if not cart:
                print('[Agent] Your cart is empty.')
                continue
            parts = []
            total = 0
            for key, val in cart.items():
                name = val['item']['name']
                qty = val['quantity']
                price = val['item']['price']
                parts.append(f"{qty} x {name} (${price:.2f})")
                total += qty * price
            print(f"[Agent] Your cart contains: {', '.join(parts)}. Total: ${total:.2f}.")
            continue
        if msg.lower() in ('place order', "i'm done", "i'm finished", "i am done"):
            if not cart:
                print('[Agent] Your cart is empty. Nothing to place.')
                continue
            name = input('[Agent] What name should I put on the order? ')
            addr = input('[Agent] What address should I deliver to? ')
            items = []
            total = 0
            for key, val in cart.items():
                items.append({'id': key, 'name': val['item']['name'], 'quantity': val['quantity'], 'unit_price': val['item']['price'], 'line_total': round(val['quantity'] * val['item']['price'], 2)})
                total += val['quantity'] * val['item']['price']
            order = {'customer_name': name or 'Guest', 'address': addr or "", 'items': items, 'total': round(total, 2), 'timestamp': datetime.now().isoformat(), 'status': 'placed'}
            filename = ORDERS_DIR / f"order_{order['customer_name'].replace(' ', '_')}_{datetime.now().strftime('%Y%m%d%H%M%S')}.json"
            with open(filename, 'w') as f:
                json.dump(order, f, indent=2)
            print(f"[Agent] Order placed for {order['customer_name']}. Total: ${order['total']:.2f}. Order id: {filename.name}")
            cart = {}
            continue
        if msg.lower() in ('exit', 'quit'):
            print('[Agent] Goodbye!')
            break
        # Default fallback: try to add item
        item = find_item(catalog, msg)
        if item:
            key = item['id']
            cart.setdefault(key, {'item': item, 'quantity': 0})
            cart[key]['quantity'] += 1
            print(f"[Agent] Added 1 x {item['name']} to your cart.")
            continue
        print("[Agent] Sorry, I didn't understand. You can say 'Add 2 bread' or 'ingredients for pasta for two' or 'Place order'.")
