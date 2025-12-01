# 🎯 Perfect 1-Minute Demo Script

**Agent**: "Hello! I'm your shopping assistant. What are you looking for today?"

**You**: "Show me all coffee mugs"

**Agent**: *[Uses list_products]* "Found 2 products:
1. Stoneware Coffee Mug - ₹800 (white)
2. Blue Ceramic Mug - ₹750 (blue)"

**You**: "Do you have any t-shirts under ₹1000?"

**Agent**: *[Uses list_products with max_price]* "Found 1 product:
1. Cotton T-Shirt - ₹899 (black)"

**You**: "I'm looking for a black hoodie"

**Agent**: *[Uses list_products with color]* "Found 1 product:
1. Black Hoodie - ₹1999 (black)"

**You**: "I'll buy the black hoodie in size M"

**Agent**: *[Uses create_order]* "Order placed successfully! 🎉
Order ID: [random-id]
Total: ₹1999
Status: CONFIRMED"

**You**: "What did I just buy?"

**Agent**: *[Uses get_last_order]* "Your last order (ID: [order-id]):
- Black Hoodie x1 - ₹1999
Total: ₹1999
Status: CONFIRMED"

---

## ✅ Primary Goal Checklist Covered:

- ✅ **Catalog Browsing**: "Show me all coffee mugs", "t-shirts under ₹1000", "black hoodie"
- ✅ **Product Filtering**: By category, price, color
- ✅ **Order Placement**: "I'll buy the black hoodie" 
- ✅ **Order Persistence**: Saves to `order_[id].json` file
- ✅ **Order History**: "What did I just buy?" shows last order
- ✅ **ACP Structure**: Separate catalog/order functions, structured JSON
- ✅ **Voice Flow**: Natural conversation with tool calls