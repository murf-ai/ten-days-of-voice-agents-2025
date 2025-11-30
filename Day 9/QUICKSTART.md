# Quick Start Guide - Day 9 E-commerce Shopping Agent

## 🚀 Get Started in 3 Steps

### Step 1: Start the Backend

```bash
cd ten-days-of-voice-agents-2025/Day\ 9/backend
uv run src/shopping_agent.py dev
```

You should see:
```
[OK] Loaded LIVEKIT_URL: wss://...
Starting E-commerce Shopping Agent
Shopping agent connected and ready
```

### Step 2: Start the Frontend

In a new terminal:

```bash
cd ten-days-of-voice-agents-2025/Day\ 7/frontend
pnpm dev
```

### Step 3: Test the Agent

1. Open http://localhost:3000
2. Click "Connect" (or "Enter the Upside Down" if using Day 8 theme)
3. Wait for the agent to greet you
4. Start shopping!

## 🎤 Example Conversations

### Browse Products

**You:** "Show me all coffee mugs"

**Agent:** "I found 3 products:
1. Stoneware Coffee Mug - ₹800 (white)
2. Blue Ceramic Mug - ₹650 (blue)
3. Black Travel Mug - ₹1200 (black)"

---

**You:** "Do you have any t-shirts under 800?"

**Agent:** "I found 2 products:
1. Classic White T-Shirt - ₹599 (white)
2. Black Graphic T-Shirt - ₹799 (black)"

---

**You:** "I'm looking for a black hoodie"

**Agent:** "I found 1 product:
1. Black Pullover Hoodie - ₹1499 (black)"

### Place an Order

**You:** "I'll buy the black hoodie in size M"

**Agent:** "Order confirmed! Order ID: a1b2c3d4

Items:
- Black Pullover Hoodie x1 (Size: M) - ₹1499

Total: ₹1499
Status: confirmed"

---

**You:** "I want 2 blue mugs"

**Agent:** "Order confirmed! Order ID: e5f6g7h8

Items:
- Blue Ceramic Mug x2 - ₹1300

Total: ₹1300
Status: confirmed"

### View Order History

**You:** "What did I just buy?"

**Agent:** "Your last order (ID: e5f6g7h8):

Items:
- Blue Ceramic Mug x2 - ₹1300

Total: ₹1300
Status: confirmed
Ordered at: 2025-11-30T12:34:56"

## 🛍️ Available Products

### Coffee Mugs (₹650-1200)
- Stoneware Coffee Mug (white) - ₹800
- Blue Ceramic Mug (blue) - ₹650
- Black Travel Mug (black) - ₹1200

### T-Shirts (₹599-899)
- Classic White T-Shirt (white) - ₹599
- Black Graphic T-Shirt (black) - ₹799
- Navy Blue Premium T-Shirt (navy blue) - ₹899

### Hoodies (₹1499-1699)
- Black Pullover Hoodie (black) - ₹1499
- Grey Zip Hoodie (grey) - ₹1699
- Navy Blue Hoodie (navy blue) - ₹1599

### Accessories (₹499-699)
- Black Baseball Cap - ₹499
- Canvas Tote Bag (beige) - ₹699

## 🔍 Search Filters

You can filter products by:

- **Category**: "Show me hoodies", "I want to see mugs"
- **Price**: "Under 1000", "Less than 800 rupees"
- **Color**: "Black hoodies", "Blue mugs"

## 📦 Order Files

Orders are saved in `backend/orders/` as JSON files:

```
backend/orders/
├── order_a1b2c3d4.json
├── order_e5f6g7h8.json
└── ...
```

Each file contains the complete order details with:
- Order ID
- Customer name (if provided)
- Items with quantities and sizes
- Total price
- Timestamp
- Status

## 🐛 Troubleshooting

### Backend won't start

**Error:** `LIVEKIT_URL not found`

**Solution:** Make sure `.env.local` exists in `backend/` directory with your API keys.

### Agent not responding

**Solution:** 
1. Check that backend terminal shows "Shopping agent connected and ready"
2. Refresh the browser page
3. Click "Connect" again

### Orders not saving

**Solution:** Check that `backend/orders/` directory exists and is writable.

## 🎯 Testing Checklist

- [ ] Browse products by category
- [ ] Filter by price
- [ ] Filter by color
- [ ] Place an order with quantity
- [ ] Place an order with size (for clothing)
- [ ] View last order
- [ ] Check order file was created in `backend/orders/`
- [ ] Place multiple orders
- [ ] Ask "What did I just buy?" after each order

## 🔄 Reset

To start fresh:

1. Stop the backend (Ctrl+C)
2. Delete all files in `backend/orders/`
3. Restart the backend

---

**Ready to shop? Start the backend and frontend, then visit http://localhost:3000!** 🛒

