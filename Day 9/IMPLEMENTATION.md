# Implementation Details - Day 9 E-commerce Shopping Agent

## 🏗️ Architecture Overview

### Three-Layer Architecture (ACP-Inspired)

```
┌─────────────────────────────────────────┐
│     Conversation Layer (Voice + LLM)    │
│  - Natural language understanding       │
│  - Voice input/output                   │
│  - Context tracking                     │
│  - shopping_agent.py                    │
└──────────────┬──────────────────────────┘
               │ Function Tools
               ▼
┌─────────────────────────────────────────┐
│      Commerce Layer (Merchant API)      │
│  - list_products()                      │
│  - create_order()                       │
│  - get_last_order()                     │
│  - merchant.py                          │
└──────────────┬──────────────────────────┘
               │ Data Access
               ▼
┌─────────────────────────────────────────┐
│         Data Layer (Persistence)        │
│  - Product catalog (PRODUCTS list)      │
│  - Order storage (JSON files)           │
│  - catalog.py                           │
└─────────────────────────────────────────┘
```

## 📦 Data Models

### Product Schema

```python
{
    "id": str,              # Unique identifier (e.g., "mug-001")
    "name": str,            # Product name
    "description": str,     # Product description
    "price": int,           # Price in INR (paise)
    "currency": str,        # "INR"
    "category": str,        # "mug", "tshirt", "hoodie", "cap", "bag"
    "attributes": {         # Optional attributes
        "color": str,
        "material": str,
        "sizes": list[str],  # For clothing
        "capacity": str,     # For mugs
        "insulated": bool,   # For travel mugs
        "adjustable": bool   # For caps
    }
}
```

### Order Schema

```python
{
    "id": str,              # 8-character UUID
    "customer_name": str,   # Optional customer name
    "items": [              # List of order items
        {
            "product_id": str,
            "product_name": str,
            "quantity": int,
            "size": str,    # Optional, for clothing
            "unit_price": int,
            "item_total": int
        }
    ],
    "total": int,           # Total price in INR
    "currency": str,        # "INR"
    "created_at": str,      # ISO 8601 timestamp
    "status": str           # "confirmed"
}
```

## 🛠️ Function Tools

### 1. `browse_catalog`

**Purpose:** Browse products with optional filters

**Implementation:**
```python
@function_tool
async def browse_catalog(
    context: RunContext,
    category: Optional[str] = None,
    max_price: Optional[int] = None,
    color: Optional[str] = None,
) -> str:
    products = list_products(category=category, max_price=max_price, color=color)
    self.last_shown_products = products  # Store for context
    # Format and return product list
```

**Key Features:**
- Filters products by category, price range, and color
- Stores results in `self.last_shown_products` for context
- Returns formatted string with product names and prices
- Limits display to 5 products to avoid overwhelming the user

### 2. `place_order`

**Purpose:** Create an order for a product

**Implementation:**
```python
@function_tool
async def place_order(
    context: RunContext,
    product_id: str,
    quantity: int = 1,
    size: Optional[str] = None,
    customer_name: Optional[str] = None,
) -> str:
    line_items = [{"product_id": product_id, "quantity": quantity}]
    if size:
        line_items[0]["size"] = size
    
    order = create_order(line_items, customer_name=self.customer_name)
    # Return formatted confirmation
```

**Key Features:**
- Validates product exists
- Supports quantity and size parameters
- Stores customer name for future orders
- Returns detailed order confirmation
- Persists order to JSON file

### 3. `view_last_order`

**Purpose:** Retrieve the most recent order

**Implementation:**
```python
@function_tool
async def view_last_order(context: RunContext) -> str:
    order = get_last_order()
    # Format and return order details
```

**Key Features:**
- Retrieves from in-memory session orders
- Returns full order details including timestamp
- Handles case when no orders exist

## 🔄 Commerce Functions (merchant.py)

### `list_products()`

**Filtering Logic:**
1. Start with full catalog
2. Apply category filter (case-insensitive)
3. Apply price range filters (min/max)
4. Apply color filter (checks attributes.color)
5. Return filtered list

**Example:**
```python
products = list_products(category="hoodie", max_price=1600, color="black")
# Returns: [Black Pullover Hoodie - ₹1499]
```

### `create_order()`

**Order Creation Flow:**
1. Generate 8-character UUID for order ID
2. For each line item:
   - Look up product by ID
   - Calculate item total (price × quantity)
   - Build order item object
3. Calculate order total
4. Create order object with timestamp
5. Append to SESSION_ORDERS (in-memory)
6. Persist to JSON file in `orders/` directory
7. Return order object

**File Naming:** `order_{order_id}.json`

### `get_last_order()`

**Retrieval Logic:**
- Returns last item from SESSION_ORDERS list
- Returns None if no orders exist
- Only accesses current session orders (not historical files)

## 🎯 Context Tracking

### Product Context

The agent tracks recently shown products in `self.last_shown_products`:

```python
# After browse_catalog
self.last_shown_products = [
    {"id": "hoodie-001", "name": "Black Pullover Hoodie", ...},
    {"id": "hoodie-002", "name": "Grey Zip Hoodie", ...},
]

# User says: "I'll buy the second one"
# LLM can resolve to product_id="hoodie-002"
```

### Customer Context

The agent stores customer name:

```python
# First order
place_order(product_id="mug-001", customer_name="John")
self.customer_name = "John"

# Subsequent orders automatically use stored name
place_order(product_id="tshirt-001")  # Uses "John"
```

## 🔐 Error Handling

### Product Not Found

```python
try:
    order = create_order(line_items)
except ValueError as e:
    return f"Sorry, I couldn't place that order: {str(e)}"
```

### No Orders Exist

```python
order = get_last_order()
if not order:
    return "You haven't placed any orders yet."
```

### General Errors

```python
except Exception as e:
    logger.error(f"Error placing order: {e}")
    return "Sorry, there was an error. Please try again."
```

## 📊 Data Flow Example

### Complete Shopping Flow

```
User: "Show me black hoodies"
  ↓
Agent calls: browse_catalog(category="hoodie", color="black")
  ↓
merchant.list_products(category="hoodie", color="black")
  ↓
Returns: [Black Pullover Hoodie - ₹1499]
  ↓
Agent stores in self.last_shown_products
  ↓
Agent says: "I found 1 product: Black Pullover Hoodie - ₹1499"

User: "I'll buy it in size M"
  ↓
Agent calls: place_order(product_id="hoodie-001", size="M")
  ↓
merchant.create_order([{"product_id": "hoodie-001", "quantity": 1, "size": "M"}])
  ↓
Generates order ID: "a1b2c3d4"
Saves to: orders/order_a1b2c3d4.json
Adds to: SESSION_ORDERS
  ↓
Returns order object
  ↓
Agent says: "Order confirmed! Order ID: a1b2c3d4..."

User: "What did I just buy?"
  ↓
Agent calls: view_last_order()
  ↓
merchant.get_last_order()
  ↓
Returns: SESSION_ORDERS[-1]
  ↓
Agent says: "Your last order (ID: a1b2c3d4): Black Pullover Hoodie..."
```

## 🎓 ACP Principles Applied

1. **Separation of Concerns**
   - Conversation logic separate from commerce logic
   - Clear API boundaries between layers

2. **Structured Data**
   - Consistent Product and Order schemas
   - JSON-based data exchange

3. **Stateful Commerce**
   - Orders persisted with unique IDs
   - Full audit trail with timestamps

4. **Intent-Based Actions**
   - Natural language → structured function calls
   - LLM interprets intent, functions execute commerce

5. **Extensibility**
   - Easy to add new products
   - Easy to add new commerce functions
   - Ready for payment integration

---

**This implementation provides a solid foundation for building production e-commerce voice agents!**

