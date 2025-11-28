# Day 7 – Food & Grocery Ordering Voice Agent

## Overview

Today you’ll build a **shopping assistant** for your favorite food ordering/quick commerce platform.

For the **primary goal**:

- You’ll create a **sample catalog** in a JSON format of your choice.
- The bot will understand what the user wants (items, quantities, or even “ingredients for X”).
- It will **add items to a cart**, keep track of the order as the conversation progresses.
- When the user is done, the final order will be **“placed” by saving it to a JSON file**.

For the **advanced goals**, you’ll build a mock **order tracking system**:

- Orders get a status that changes over time (mocked).
- The agent can answer “where is my order?” by checking this status.
- The agent has access to **previous orders**, not just the current one.

All persistence should be done using **JSON files or a database**

---

## What You’ll Work With

You will typically have:

- A **catalog JSON file** that you will design and create.
- One or more **order JSON files** for storing placed orders and order history.

Use JSON files for input (catalog) and output (orders, history, tracking).

---

## Primary Goal (MVP) – Food & Grocery Ordering + Cart → Order JSON

**Objective:**  
Build a voice agent that lets a user order food and groceries from a catalog, intelligently adds items to a cart (including bundled ingredients), keeps track of the order, and saves the final order to a JSON file when the user is done.

### Tasks

1. **Create a catalog JSON file**

   - Design a JSON file (name of your choice) that describes your **food and grocery catalog**.
   - Include multiple categories, for example:
     - Groceries (bread, eggs, milk, etc.)
     - Snacks
     - Prepared food (pizzas, sandwiches, etc.)
   - Each item should have sensible fields, such as:
     - Item name
     - Category
     - Price
     - Optional attributes (brand, size, units, tags like “vegan”, “gluten-free”, etc.)
   - Keep it small but diverse enough (at least 10–20 items) to make the conversation interesting.

2. **Set up the ordering assistant persona**

   - Make the agent behave like a **friendly food & grocery ordering assistant** for a fictional brand or store.
   - It should:
     - Greet the user and explain what it can do (e.g. “I can help you order groceries and simple meal ingredients.”).
     - Ask for clarifications when needed (size, brand, quantity, etc.).

3. **Implement cart management**

   - Maintain a **cart** in scenario state that can store:
     - Items selected
     - Quantities
     - Any relevant notes or options (e.g. “whole wheat bread”, “large peanut butter”).
   - Support basic operations:
     - Adding items (with quantity).
     - Removing items.
     - Updating quantities.
     - Listing what’s currently in the cart when asked (“What’s in my cart?”).
   - Ensure the agent confirms key cart changes verbally so users know what’s happening.

4. **Handle “ingredients for X” style requests intelligently**

   - The agent should be able to understand **higher-level intents**, such as:
     - “I need ingredients for a peanut butter sandwich.”
     - “Get me what I need for making pasta for two people.”
   - For these requests:
     - Map the request to **multiple items** in your catalog (e.g. bread + peanut butter, or pasta + sauce, etc.).
     - Add all relevant items to the cart, and verbally confirm:
       - “I’ve added bread and peanut butter to your cart for your sandwich.”
   - You can:
     - Hard-code a small “recipes” mapping (dish → list of items).
     - Or infer items based on tags in your catalog.
   - This is the key “intelligent” behavior for the Day 7 primary goal.

5. **Place the order and save it to a JSON file**

   - Detect when the user is done ordering, for example when they say:
     - “That’s all.” / “Place my order.” / “I’m done.”
   - At that point:
     - Confirm the final cart contents and total in conversation.
     - Create an **order object in memory** containing:
       - Items (with quantities and prices).
       - Order total.
       - Timestamp.
       - Any simple customer info you choose to capture (e.g. name or address as text).
     - Save this order data to a **JSON file**:
       - You can choose the filename (for example, a single `current_order.json` or a new file per order).
   - After saving:
     - Let the user know the order has been placed and stored.

### MVP Completion Checklist

You’ve completed the **primary goal** if:

- You created a catalog JSON file with a variety of food and grocery items.
- The agent can:
  - Add specific items and quantities to a cart.
  - Intelligently add multiple items for simple “ingredients for X” requests.
  - Show/list the cart when asked.
- When the user is done:
  - The agent confirms the final order.
  - The order is written to a JSON file (representing “order placed”).

**Note: You can use JSON or a database. You are not restricted to use database**

#### Resources
- https://docs.livekit.io/agents/build/prompting/
- https://docs.livekit.io/agents/build/tools/
---

## Advanced Goals (Optional, Higher Impact)

The main advanced goal for Day 7 is to build a **mock order tracking** solution:

- After placing an order (saved to JSON/Database), its status should **change over time**.
- The agent should be able to read order statuses from JSON/Database and answer tracking questions.
- The agent should have access to **previous orders**, not just the latest one.

You can add additional advanced features on top.

---

### Advanced Goal 1 (Main) – Mock Order Tracking Over Time

**Objective:**  
Create a simple order tracking system where placed orders transition through statuses over time, stored and updated in JSON/Database.

**Tasks:**

- Decide on a set of order statuses, for example:
  - “received”
  - “confirmed”
  - “being_prepared”
  - “out_for_delivery”
  - “delivered”
- When an order is placed:
  - Save it with an initial status (e.g. “received”) in a JSON/Database structure that can hold multiple orders.
- Implement a way for the status to **change over time** (mocked), for example:
  - A manual trigger you can call from the server or console.
  - A simple time-based check where the status advances after some time has passed.
- Ensure the agent can:
  - Look up the current status of the latest order.
  - Answer questions like:
    - “Where is my order?”
    - “Has my order been delivered?”
- Persist the updated status back to the JSON/Database file each time it changes.

---

### Advanced Goal 2 – Order History and Previous Orders

**Objective:**  
Keep a **history** of all orders in JSON/Database and let the agent access it in conversation.

**Tasks:**

- Instead of overwriting a single order file:
  - Store **all orders** in one JSON/Database file (a list) or one file per order.
- Ensure each order has:
  - A unique ID or identifier.
  - A timestamp.
  - Status.
  - Items and total.
- Teach the agent to:
  - Answer questions like:
    - “What did I order last time?”
    - “Have I ordered apples before?”
    - “Show me my most recent order.”
  - Refer to the stored JSON/Database history when answering these questions.
- Continue to update status in the history JSON/Database, not just for the current order.

---

### Advanced Goal 3 – Multiple Concurrent Orders

**Objective:**  
Support multiple active orders for the same user and allow tracking specific ones.

**Tasks:**

- Allow the user to place more than one order over time (e.g. groceries today, restaurant food later).
- Keep all active orders in your order history JSON/Database with:
  - Distinct IDs.
  - Possibly a label or type (e.g. “grocery”, “restaurant”).
- Enable the agent to:
  - Distinguish between orders when asked:
    - “Track my grocery order.”
    - “What’s the status of my last restaurant order?”
  - Ask clarifying questions when there’s ambiguity (“Do you mean the order from this morning or the one from last night?”).
- Update and persist statuses for multiple active orders.

---

### Advanced Goal 4 – Smart Reorder / Recommendations from History

**Objective:**  
Use past orders stored in JSON/Database to recommend items or re-build carts.

**Tasks:**

- Analyze the order history JSON/Database to identify:
  - Frequently ordered items.
  - Recent orders.
- Allow the user to say:
  - “Reorder what I got last time.”
  - “Get me my usual groceries.”
- Have the agent:
  - Build a new cart based on a previous order.
  - Optionally suggest related items (“You usually order milk with that. Add it again?”).
- Save this new order as usual, with its own ID and status progression.

---

### Advanced Goal 5 – Budget or Constraints-Aware Ordering

**Objective:**  
Add simple constraints (like budget or dietary tags) that influence what goes into the cart.

**Tasks:**

- Allow the user to specify constraints such as:
  - “Keep it under 1000.”
  - “Only vegan items.”
- Use your catalog JSON fields (price, tags, etc.) to:
  - Filter items based on the constraint.
  - Warn the user when constraints can’t be fully met.
- Make sure the agent:
  - Tries to build carts that respect these constraints.
  - Verbally explains when something might exceed budget or violate a constraint.

-----

- Step 1: You only need the **primary goal** to complete Day 7; the **Advanced Goals** are for going the extra mile.
- Step 2: **Successfully connect to Food & Grocery Ordering Voice Agent** in your browser and go through ordering process of adding, updating and removing items.
- Step 3: **Record a short video** of your session with the agent and show the final order JSON.
- Step 4: **Post the video on LinkedIn** with a description of what you did for the task on Day 7. Also, mention that you are building voice agent using the fastest TTS API - Murf Falcon. Mention that you are part of the **“Murf AI Voice Agent Challenge”** and don't forget to tag the official Murf AI handle. Also, use hashtags **#MurfAIVoiceAgentsChallenge** and **#10DaysofAIVoiceAgents**

Once your agent is running and your LinkedIn post is live, you’ve completed Day 7.