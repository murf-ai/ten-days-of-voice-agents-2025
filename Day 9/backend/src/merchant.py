"""
Merchant Layer - ACP-inspired commerce functions
Handles product catalog browsing and order creation
"""

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from catalog import PRODUCTS, get_product_by_id

# Orders storage
ORDERS_DIR = Path(__file__).parent.parent / "orders"
ORDERS_DIR.mkdir(exist_ok=True)

# In-memory orders for current session
SESSION_ORDERS = []


def list_products(
    category: Optional[str] = None,
    max_price: Optional[int] = None,
    color: Optional[str] = None,
    min_price: Optional[int] = None,
) -> list[dict]:
    """
    List products with optional filters
    
    Args:
        category: Filter by category (e.g., "mug", "tshirt", "hoodie")
        max_price: Maximum price in INR
        color: Filter by color
        min_price: Minimum price in INR
    
    Returns:
        List of matching products
    """
    filtered_products = PRODUCTS.copy()
    
    # Apply category filter
    if category:
        category_lower = category.lower()
        filtered_products = [
            p for p in filtered_products 
            if p["category"].lower() == category_lower
        ]
    
    # Apply price filters
    if max_price is not None:
        filtered_products = [
            p for p in filtered_products 
            if p["price"] <= max_price
        ]
    
    if min_price is not None:
        filtered_products = [
            p for p in filtered_products 
            if p["price"] >= min_price
        ]
    
    # Apply color filter
    if color:
        color_lower = color.lower()
        filtered_products = [
            p for p in filtered_products 
            if p.get("attributes", {}).get("color", "").lower() == color_lower
        ]
    
    return filtered_products


def create_order(line_items: list[dict], customer_name: Optional[str] = None) -> dict:
    """
    Create an order from line items
    
    Args:
        line_items: List of items like [{"product_id": "mug-001", "quantity": 2, "size": "M"}]
        customer_name: Optional customer name
    
    Returns:
        Order object with id, items, total, currency, created_at
    """
    order_id = str(uuid.uuid4())[:8]
    order_items = []
    total_price = 0
    currency = "INR"
    
    for item in line_items:
        product_id = item.get("product_id")
        quantity = item.get("quantity", 1)
        size = item.get("size")
        
        # Look up product
        product = get_product_by_id(product_id)
        if not product:
            raise ValueError(f"Product {product_id} not found")
        
        # Calculate item total
        item_total = product["price"] * quantity
        total_price += item_total
        
        # Build order item
        order_item = {
            "product_id": product_id,
            "product_name": product["name"],
            "quantity": quantity,
            "unit_price": product["price"],
            "item_total": item_total,
        }
        
        # Add size if specified
        if size:
            order_item["size"] = size
        
        order_items.append(order_item)
    
    # Create order object
    order = {
        "id": order_id,
        "customer_name": customer_name,
        "items": order_items,
        "total": total_price,
        "currency": currency,
        "created_at": datetime.now().isoformat(),
        "status": "confirmed"
    }
    
    # Save to session
    SESSION_ORDERS.append(order)
    
    # Persist to file
    order_file = ORDERS_DIR / f"order_{order_id}.json"
    with open(order_file, "w") as f:
        json.dump(order, f, indent=2)
    
    return order


def get_last_order() -> Optional[dict]:
    """Get the most recent order from the current session"""
    if SESSION_ORDERS:
        return SESSION_ORDERS[-1]
    return None


def get_order_by_id(order_id: str) -> Optional[dict]:
    """Get an order by ID from file"""
    order_file = ORDERS_DIR / f"order_{order_id}.json"
    if order_file.exists():
        with open(order_file, "r") as f:
            return json.load(f)
    return None

