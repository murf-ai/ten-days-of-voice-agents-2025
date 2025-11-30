# Day 9 - E-commerce Voice Shopping Agent

A voice-driven shopping assistant built following the **Agentic Commerce Protocol (ACP)** principles.

## 🎯 Overview

This agent allows customers to:
- Browse products by voice ("Show me all coffee mugs")
- Filter by category, price, and color
- Place orders with natural language ("I'll buy the second hoodie in size M")
- View order history ("What did I just buy?")

## 🏗️ Architecture (ACP-Inspired)

### Separation of Concerns

1. **Conversation Layer** (LLM + Voice)
   - Natural language understanding
   - Voice input/output
   - Context tracking

2. **Commerce Layer** (Merchant Functions)
   - `list_products()` - Browse catalog with filters
   - `create_order()` - Create and persist orders
   - `get_last_order()` - Retrieve order history

3. **Data Layer**
   - Product catalog (structured JSON)
   - Order persistence (JSON files)

### ACP Principles Applied

- ✅ **Structured Data Models**: Products and Orders follow consistent schemas
- ✅ **Clear API Boundaries**: Merchant functions separate from conversation logic
- ✅ **Stateful Commerce**: Orders persisted with IDs, timestamps, and full details
- ✅ **Intent-Based Shopping**: Natural language → structured commerce actions

## 📦 Product Catalog

### Categories

- **Coffee Mugs** (₹650-1200)
  - Ceramic mugs, travel mugs
  - Colors: white, blue, black
  
- **T-Shirts** (₹599-899)
  - Cotton and premium cotton
  - Colors: white, black, navy blue
  - Sizes: S, M, L, XL

- **Hoodies** (₹1499-1699)
  - Pullover and zip styles
  - Colors: black, grey, navy blue
  - Sizes: S, M, L, XL

- **Accessories** (₹499-699)
  - Baseball caps, tote bags

### Product Schema

```json
{
  "id": "mug-001",
  "name": "Stoneware Coffee Mug",
  "description": "Classic ceramic coffee mug",
  "price": 800,
  "currency": "INR",
  "category": "mug",
  "attributes": {
    "color": "white",
    "material": "ceramic",
    "capacity": "350ml"
  }
}
```

## 🛒 Order Schema

```json
{
  "id": "a1b2c3d4",
  "customer_name": "John Doe",
  "items": [
    {
      "product_id": "hoodie-001",
      "product_name": "Black Pullover Hoodie",
      "quantity": 1,
      "size": "M",
      "unit_price": 1499,
      "item_total": 1499
    }
  ],
  "total": 1499,
  "currency": "INR",
  "created_at": "2025-11-30T12:00:00",
  "status": "confirmed"
}
```

## 🎤 Voice Interactions

### Browse Products

**User:** "Show me all coffee mugs"
**Agent:** Calls `browse_catalog(category="mug")` and lists products

**User:** "Do you have any t-shirts under 1000?"
**Agent:** Calls `browse_catalog(category="tshirt", max_price=1000)`

**User:** "I'm looking for a black hoodie"
**Agent:** Calls `browse_catalog(category="hoodie", color="black")`

### Place Orders

**User:** "I'll buy the second hoodie you mentioned, in size M"
**Agent:** 
- Resolves "second hoodie" from context
- Calls `place_order(product_id="hoodie-002", size="M")`
- Confirms order details

**User:** "I want 2 blue mugs"
**Agent:** Calls `place_order(product_id="mug-002", quantity=2)`

### View Orders

**User:** "What did I just buy?"
**Agent:** Calls `view_last_order()` and reads back order details

## 🚀 Quick Start

### 1. Install Dependencies

```bash
cd backend
uv sync
```

### 2. Configure Environment

Copy `.env.example` to `.env.local` and add your API keys:

```bash
cp .env.example .env.local
```

### 3. Run the Agent

```bash
uv run src/shopping_agent.py dev
```

### 4. Connect Frontend

Use the Day 7 frontend (already configured):

```bash
cd ../../Day\ 7/frontend
pnpm dev
```

Visit http://localhost:3000 and click "Connect"

## 🛠️ Function Tools

### `browse_catalog`

Browse products with optional filters.

**Parameters:**
- `category` (optional): "mug", "tshirt", "hoodie", "cap", "bag"
- `max_price` (optional): Maximum price in INR
- `color` (optional): Color filter

**Returns:** List of matching products

### `place_order`

Create an order for a product.

**Parameters:**
- `product_id` (required): Product ID (e.g., "mug-001")
- `quantity` (optional): Number of items (default: 1)
- `size` (optional): Size for clothing (S, M, L, XL)
- `customer_name` (optional): Customer's name

**Returns:** Order confirmation with ID and details

### `view_last_order`

View the most recent order.

**Returns:** Last order details or message if no orders exist

## 📁 Project Structure

```
Day 9/
├── backend/
│   ├── src/
│   │   ├── shopping_agent.py    # Main agent with voice integration
│   │   ├── catalog.py            # Product catalog
│   │   ├── merchant.py           # Commerce functions
│   │   └── __init__.py
│   ├── orders/                   # Persisted orders (JSON files)
│   ├── pyproject.toml            # Dependencies
│   ├── .env.local                # API keys (not in git)
│   └── .env.example              # Template
└── README.md
```

## ✅ Requirements Checklist

- ✅ Small product catalog (11 products across 4 categories)
- ✅ ACP-inspired merchant layer (catalog.py, merchant.py)
- ✅ Voice flow for browsing and ordering
- ✅ Orders persisted to JSON files
- ✅ Browse catalog by voice with filters
- ✅ Place orders with natural language
- ✅ View last order functionality
- ✅ Structured Product and Order schemas
- ✅ Separation of conversation and commerce logic

## 🎓 What You Learned

1. **ACP Principles**: Separation of conversation, commerce, and data layers
2. **Structured Commerce**: Product and Order data models
3. **Function Tools**: LLM calling Python functions for commerce operations
4. **Context Tracking**: Resolving "the second one" from conversation history
5. **Order Persistence**: Saving orders with unique IDs and timestamps

## 🔄 Next Steps

- Add more products to the catalog
- Implement cart functionality (multiple items before checkout)
- Add order cancellation
- Integrate real payment processing
- Add inventory management
- Implement full ACP specification

---

**Built with:** LiveKit Agents, Google Gemini 2.0, Deepgram Nova-3, Murf TTS

