"""
Product Catalog - ACP-inspired data model
Manages the product catalog for the e-commerce voice agent
"""

from typing import Optional

# Product Catalog - ACP-inspired structure
PRODUCTS = [
    # Coffee Mugs
    {
        "id": "mug-001",
        "name": "Stoneware Coffee Mug",
        "description": "Classic ceramic coffee mug with smooth finish",
        "price": 800,
        "currency": "INR",
        "category": "mug",
        "attributes": {
            "color": "white",
            "material": "ceramic",
            "capacity": "350ml"
        }
    },
    {
        "id": "mug-002",
        "name": "Blue Ceramic Mug",
        "description": "Beautiful blue glazed ceramic mug",
        "price": 650,
        "currency": "INR",
        "category": "mug",
        "attributes": {
            "color": "blue",
            "material": "ceramic",
            "capacity": "300ml"
        }
    },
    {
        "id": "mug-003",
        "name": "Black Travel Mug",
        "description": "Insulated stainless steel travel mug",
        "price": 1200,
        "currency": "INR",
        "category": "mug",
        "attributes": {
            "color": "black",
            "material": "stainless steel",
            "capacity": "500ml",
            "insulated": True
        }
    },
    
    # T-Shirts
    {
        "id": "tshirt-001",
        "name": "Classic White T-Shirt",
        "description": "100% cotton white t-shirt",
        "price": 599,
        "currency": "INR",
        "category": "tshirt",
        "attributes": {
            "color": "white",
            "material": "cotton",
            "sizes": ["S", "M", "L", "XL"]
        }
    },
    {
        "id": "tshirt-002",
        "name": "Black Graphic T-Shirt",
        "description": "Cotton t-shirt with cool graphic design",
        "price": 799,
        "currency": "INR",
        "category": "tshirt",
        "attributes": {
            "color": "black",
            "material": "cotton",
            "sizes": ["S", "M", "L", "XL"]
        }
    },
    {
        "id": "tshirt-003",
        "name": "Navy Blue Premium T-Shirt",
        "description": "Premium quality navy blue t-shirt",
        "price": 899,
        "currency": "INR",
        "category": "tshirt",
        "attributes": {
            "color": "navy blue",
            "material": "premium cotton",
            "sizes": ["M", "L", "XL"]
        }
    },
    
    # Hoodies
    {
        "id": "hoodie-001",
        "name": "Black Pullover Hoodie",
        "description": "Comfortable black hoodie with front pocket",
        "price": 1499,
        "currency": "INR",
        "category": "hoodie",
        "attributes": {
            "color": "black",
            "material": "cotton blend",
            "sizes": ["M", "L", "XL"]
        }
    },
    {
        "id": "hoodie-002",
        "name": "Grey Zip Hoodie",
        "description": "Grey hoodie with full zip and pockets",
        "price": 1699,
        "currency": "INR",
        "category": "hoodie",
        "attributes": {
            "color": "grey",
            "material": "cotton blend",
            "sizes": ["S", "M", "L", "XL"]
        }
    },
    {
        "id": "hoodie-003",
        "name": "Navy Blue Hoodie",
        "description": "Navy blue pullover hoodie",
        "price": 1599,
        "currency": "INR",
        "category": "hoodie",
        "attributes": {
            "color": "navy blue",
            "material": "cotton blend",
            "sizes": ["M", "L", "XL"]
        }
    },
    
    # Accessories
    {
        "id": "cap-001",
        "name": "Black Baseball Cap",
        "description": "Classic black baseball cap",
        "price": 499,
        "currency": "INR",
        "category": "cap",
        "attributes": {
            "color": "black",
            "material": "cotton",
            "adjustable": True
        }
    },
    {
        "id": "bag-001",
        "name": "Canvas Tote Bag",
        "description": "Eco-friendly canvas tote bag",
        "price": 699,
        "currency": "INR",
        "category": "bag",
        "attributes": {
            "color": "beige",
            "material": "canvas",
            "capacity": "15L"
        }
    },
]


def get_product_by_id(product_id: str) -> Optional[dict]:
    """Get a single product by ID"""
    for product in PRODUCTS:
        if product["id"] == product_id:
            return product
    return None

