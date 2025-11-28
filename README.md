# Food & Grocery Ordering Voice Agent

This project implements a voice agent for ordering food and groceries. The agent can understand natural language requests, maintain a cart, handle recipe ingredients, place orders, and track order status.

## Features

### Primary Features
- Browse and order from a catalog of food and grocery items
- Add items to cart with specified quantities
- Request ingredients for recipes (e.g., "ingredients for a peanut butter sandwich")
- View cart contents
- Place orders and save them to JSON files

### Advanced Features
- Order tracking system that simulates status updates
- Access to order history
- Check status of current and previous orders

## Getting Started

### Prerequisites
- Python 3.6 or higher

### Installation
1. Clone this repository
2. No additional packages are required as this uses only standard Python libraries

### Running the Agent
```bash
python main.py
```

## Usage Examples

Here are some examples of commands you can use with the voice agent:

### Basic Commands
- "Hello" - Greet the agent
- "Add milk to my cart" - Add an item to your cart
- "Add 2 apples to my cart" - Add multiple items
- "What's in my cart?" - Check your current cart
- "Remove eggs from my cart" - Remove an item
- "Place my order" - Place your order

### Recipe Requests
- "I need ingredients for a peanut butter sandwich"
- "Get me ingredients for pasta dinner for two"

### Order Tracking
- "Where is my order?" - Check status of your most recent order
- "What's the status of my order?" - Same as above
- "What's the status of order [order-id]?" - Check status of a specific order
- "Show my previous orders" - View order history

## Project Structure

- `main.py` - Main entry point for the voice agent
- `grocery_agent.py` - Core functionality for the grocery ordering agent
- `catalog.json` - Food and grocery catalog
- `orders/` - Directory where orders and order history are stored

## How It Works

1. The agent loads a catalog of food and grocery items from `catalog.json`
2. Users can interact with the agent using natural language commands
3. The agent maintains a cart of items during the conversation
4. When an order is placed, it's saved to a JSON file in the `orders/` directory
5. Order status is updated over time (simulated for demo purposes)
6. Users can check the status of their orders at any time