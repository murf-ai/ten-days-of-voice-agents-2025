# Day 9 – E-commerce Agent (Based on the Agentic Commerce Protocol)

Today you will build a **voice-driven shopping assistant** that follows a very lite version of the [Agentic Commerce Protocol (ACP)](https://www.agenticcommerce.dev/).

The idea is to simulate the key ACP pattern:

- The **user** describes what they want to buy.
- The **AI agent** interprets that intent.
- The agent calls a **merchant-like API** (your Python code) to:
  - Browse a product catalog.
  - Create an order.

No real payments, authentication, or full spec are required for this day.

---

## ACP: Very Short Primer (Conceptual)

The Agentic Commerce Protocol (ACP) is an open standard that defines how:

- **Buyers and their AI agents** express shopping intent,
- **Merchants** expose their products and create orders,
- **Payment providers** process the payment securely,

using a structured, JSON-based interface and HTTP APIs.

Key ideas you should borrow for this task:

- Keep a **clear separation** between:
  - Conversation (LLM + voice),
  - Commerce logic (functions/endpoints that manage catalog and orders).
- Use **structured objects** for:
  - Product catalog items,
  - Orders (what was bought, quantity, price, currency).

You are not implementing the full ACP spec.  
You are just building a small, ACP-inspired flow in your own code.

---

## Primary Goal (Required)

Build a **voice shopping assistant** with:

1. A small product catalog.
2. A simple, ACP-inspired “merchant layer” in Python.
3. A voice flow that lets the user browse and place an order.
4. Orders persisted on the backend (in memory or JSON file).

### Behaviour Requirements

Your agent should:

1. Let the user explore the catalog by voice

   Examples (not hard-coded phrases):

   - “Show me all coffee mugs.”
   - “Do you have any t-shirts under 1000?”
   - “I’m looking for a black hoodie.”
   - "Does this coffee mug come in blue?"

   The agent should:

   - Call a Python function to get the catalog or filtered list.
   - Summarize a few relevant products with name and price.

2. Allow the user to place an order

   Example flow:

   - User: “I’ll buy the second hoodie you mentioned, in size M.”
   - Agent:
     - Resolves which product this refers to.
     - Calls a Python function to create an order object.
     - Confirms the order details back to the user.

3. Persist orders in a simple backend structure

   For the primary goal, it is enough to:

   - Keep an in-memory list of orders per session, or
   - Append to a `orders.json` file.

   Each order should at least include:

   - A generated order ID.
   - Product ID(s).
   - Quantity.
   - Price and currency.
   - Timestamp.

4. Provide a minimal way to view the last order

   Examples:

   - User: “What did I just buy?”
   - Agent reads back the most recent order summary from the backend.

### Data Model Requirements

Keep the schema simple but structured. For example:

- Product:
  - `id`, `name`, `description`, `price`, `currency`, `category`, optional attributes (color, size, etc.).
- Order:
  - `id`, `items` (list of product IDs + quantities), `total`, `currency`, `created_at`.

You can store the catalog in a static Python list or a JSON file.

### Minimal Python Scaffolding (Example)

You are free to design your own shapes.  
The following is only a guiding example of how to organize things:

```python
# example_catalog.py (guidance only)
PRODUCTS = [
    {
        "id": "mug-001",
        "name": "Stoneware Coffee Mug",
        "price": 800,
        "currency": "INR",
        "category": "mug",
        "color": "white",
    },
    # Add a few more products...
]

ORDERS = []

def list_products(filters: dict | None = None) -> list[dict]:
    # Apply naive filtering by category, max_price, color, etc.
    # Return a list of products.
    ...

def create_order(line_items: list[dict]) -> dict:
    # line_items: [{ "product_id": "...", "quantity": 1 }, ...]
    # Look up products, compute total, create an order dict,
    # append to ORDERS, and return the order.
    ...
```

From your LLM tool-calling layer, you should be calling functions like `list_products` and `create_order` instead of handling catalog/order logic inside the prompt.

---

## Advanced Goals (Optional)

The advanced goals are about moving from a “lite” ACP-inspired flow toward something closer to a real ACP-style integration.

You can pick any subset of these goals.

---

### Advanced Goal 1: ACP-Style Merch API + UI “Click to Buy”

Implement a more structured “merchant API” and a simple UI product list where the user can click to buy.

Requirements:

1. Expose HTTP endpoints (or equivalent function router) on the backend inspired by ACP ideas:

   - `GET /acp/catalog` – returns products as JSON.
   - `POST /acp/orders` – accepts an order payload and returns an order object.

2. In React:

   - Render the product catalog in a list/grid using the backend endpoint.
   - Add a simple “Buy” or “Add to cart” button for each product.
   - When the user clicks “Buy”, send a request that creates an order via the ACP-style endpoint.

3. Keep the voice assistant integrated:

   - The user can still place orders by voice.
   - The UI buttons are an alternative path, not a replacement.

You do not need payment forms or real checkout. Confirming the order in your UI and logs is enough.

---

### Advanced Goal 2: Closer Alignment with ACP Data Shapes

Rather than inventing your own JSON from scratch, move your models a bit closer to ACP-style shapes.

Ideas:

- Introduce a `line_items` list in orders:

  - Each with `product_id`, `quantity`, `unit_amount`, `currency`.

- Include buyer info:

  - A simple `buyer` object with name or email.

- Add an order `status` field:

  - Possible values like `PENDING`, `CONFIRMED`, `CANCELLED`.

You do not need to fully implement the official schemas, but use them as inspiration for naming and structure (e.g., line items, totals, currency fields).

---

### Advanced Goal 3: Cart and Multi-Step Flow

Move from “single-shot order” to a minimal shopping cart.

Examples:

1. Cart operations:

   - “Add this mug to my cart.”
   - “Remove the t-shirt from my cart.”
   - “What’s in my cart right now?”

2. Checkout step:

   - After the user says “checkout”, call `create_order` with the cart contents.
   - Reset the cart after successful order creation.

Backend:

- Maintain a per-session cart structure.
- Only convert the cart into an order when the user confirms.

---

### Advanced Goal 4: Order History and Status Queries

Add a minimal order history/query capability.

Examples:

- “What have I bought from you before?”
- “Show me the last 3 orders.”
- “What’s the total I spent today?”

Backend:

- Keep all orders in a JSON file or database-like structure.
- Implement simple query functions:

  - List all orders.
  - Filter by date/time.
  - Compute aggregated totals (e.g., sum of totals for a time range).

The assistant should be able to answer these questions using those functions.

---

### Advanced Goal 5: Experiment with a Type-Safe ACP Library (Optional)

If you want to go deeper into ACP itself, you can experiment with an existing ACP library in Python that provides typed models for the protocol.

For example:

- Use the library’s data classes / models for:

  - Product-like entities.
  - Orders / line items.

- Serialize and log requests/responses in a way that resembles what a real ACP merchant or client might send.

This is optional and primarily useful if you are curious about real-world ACP integrations.

---

## Implementation Notes (Non-binding)

- Backend:

  - Separate:

    - Conversation logic (LLM/tool calls),
    - Commerce logic (catalog, cart, orders).

  - Start with function calls for the primary goal.
  - Add HTTP endpoints later for advanced goals.

- Frontend:

  - For the primary goal:

    - Simple transcript area and an optional “Last order summary” panel is enough.

  - For advanced goals:

    - Add a basic product list with “Buy” buttons.
    - No need to over-design the UI; focus on correctness and flow.

Start simple: get the catalog and voice ordering working end-to-end.
Then gradually move toward ACP-inspired structure and UI once the basics are solid.

## References

- [Agentic Commerce Protocol](https://www.agenticcommerce.dev/)
- [Agentic Commerce Protocol GitHub](https://github.com/agentic-commerce-protocol/agentic-commerce-protocol)
- [OpenAI ACP Docs](https://developers.openai.com/commerce)
- https://docs.livekit.io/agents/build/tools/
- https://docs.livekit.io/home/client/data/text-streams/
- https://docs.livekit.io/home/client/data/rpc/

-----

- Step 1: You only need the **primary goal** to complete Day 9; the **Advanced Goals** are for going the extra mile.
- Step 2: **Successfully connect to E-commerce Agent** in your browser, browse product catalog and place order.
- Step 3: **Record a short video** of your session with the agent and show the order JSON file.
- Step 4: **Post the video on LinkedIn** with a description of what you did for the task on Day 9. Also, mention that you are building voice agent using the fastest TTS API - Murf Falcon. Mention that you are part of the **“Murf AI Voice Agent Challenge”** and don't forget to tag the official Murf AI handle. Also, use hashtags **#MurfAIVoiceAgentsChallenge** and **#10DaysofAIVoiceAgents**

Once your agent is running and your LinkedIn post is live, you’ve completed Day 9.