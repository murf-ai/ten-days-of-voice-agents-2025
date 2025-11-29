import logging
import json
import os
from datetime import datetime
from typing import Annotated, Literal, Any, Dict, cast
from dataclasses import dataclass, field

from dotenv import load_dotenv
from pydantic import Field
from livekit.agents import (
    Agent,
    AgentSession,
    JobContext,
    JobProcess,
    RoomInputOptions,
    WorkerOptions,
    cli,
    metrics,
    MetricsCollectedEvent,
    RunContext,
    function_tool,
)
from livekit.plugins import murf, silero, google, deepgram, noise_cancellation
from livekit.plugins.turn_detector.multilingual import MultilingualModel

logger = logging.getLogger("agent")
load_dotenv(".env.local")

@dataclass
class OrderState:
    drinkType: str | None = None
    size: str | None = None
    milk: str | None = None
    extras: list[str] = field(default_factory=lambda: [])
    name: str | None = None
    
    def is_complete(self) -> bool:
        return all([
            self.drinkType is not None,
            self.size is not None,
            self.milk is not None,
            self.name is not None
        ])

@dataclass
class Userdata:
    order: OrderState
    session_start: datetime = field(default_factory=datetime.now)

def generate_beverage_html(order: OrderState) -> str:
    size_map = {"small": "120px", "medium": "150px", "large": "180px", "extra large": "220px"}
    drink_colors = {
        "latte": "#D2B48C", "cappuccino": "#8B4513", "americano": "#654321",
        "espresso": "#2F1B14", "mocha": "#7B3F00", "coffee": "#6F4E37",
        "cold brew": "#4A4A4A", "matcha": "#7CB342"
    }
    
    cup_height = size_map.get(order.size or "medium", "150px")
    drink_color = drink_colors.get(order.drinkType or "coffee", "#6F4E37")
    has_whipped = "whipped cream" in (order.extras or [])
    
    whipped_cream = '<div style="width:80%;height:20px;background:#FFF;border-radius:50px;margin:0 auto -10px;"></div>' if has_whipped else ""
    
    return f'''<!DOCTYPE html>
<html><head><title>Order Visualization</title></head>
<body style="display:flex;justify-content:center;align-items:center;height:100vh;background:#f5f5f5;font-family:Arial;">
<div style="text-align:center;">
<h2>{order.name}'s Order</h2>
<div style="width:100px;height:{cup_height};background:linear-gradient(to bottom, {drink_color} 70%, #8B4513 100%);border:3px solid #333;border-radius:0 0 20px 20px;margin:20px auto;position:relative;">
{whipped_cream}
</div>
<p><strong>{order.size} {order.drinkType}</strong></p>
<p>Milk: {order.milk}</p>
<p>Extras: {', '.join(order.extras) if order.extras else 'None'}</p>
</div></body></html>'''

def save_order_to_json(order: OrderState) -> None:
    try:
        orders_file = "orders.json"
        orders: list[Dict[str, Any]] = []
        
        if os.path.exists(orders_file):
            with open(orders_file, 'r') as f:
                orders = json.load(f)
        
        order_data: Dict[str, Any] = {
            "drinkType": order.drinkType,
            "size": order.size,
            "milk": order.milk,
            "extras": order.extras,
            "name": order.name,
            "timestamp": datetime.now().isoformat()
        }
        orders.append(order_data)
        
        with open(orders_file, 'w') as f:
            json.dump(orders, f, indent=2)
            
        # Generate HTML visualization
        html_content = generate_beverage_html(order)
        html_filename = f"order_{order.name}_{datetime.now().strftime('%H%M%S')}.html"
        with open(html_filename, 'w') as f:
            f.write(html_content)
            
        # Try to open the HTML file automatically
        import webbrowser
        try:
            file_path = os.path.abspath(html_filename)
            webbrowser.open(f'file://{file_path}')
        except Exception:
            pass
            
        logger.info(f"Order and visualization saved for {order.name} at {html_filename}")
    except Exception as e:
        logger.error(f"Failed to save order: {e}")

@function_tool
async def set_drink_type(
    ctx: RunContext[Userdata],
    drink: Annotated[
        Literal["latte", "cappuccino", "americano", "espresso", "mocha", "coffee", "cold brew", "matcha"],
        Field(description="The type of coffee drink the customer wants"),
    ],
) -> str:
    ctx.userdata.order.drinkType = drink
    return f"Excellent choice! One {drink} coming up!"

@function_tool
async def set_size(
    ctx: RunContext[Userdata],
    size: Annotated[
        Literal["small", "medium", "large", "extra large"],
        Field(description="The size of the drink"),
    ],
) -> str:
    ctx.userdata.order.size = size
    return f"{size.title()} size - perfect!"

@function_tool
async def set_milk(
    ctx: RunContext[Userdata],
    milk: Annotated[
        Literal["whole", "skim", "almond", "oat", "soy", "coconut", "none"],
        Field(description="The type of milk for the drink"),
    ],
) -> str:
    ctx.userdata.order.milk = milk
    if milk == "none":
        return "Got it! Black coffee - strong and simple!"
    return f"{milk.title()} milk - great choice!"

@function_tool
async def set_extras(
    ctx: RunContext[Userdata],
    extras: Annotated[
        list[Literal["sugar", "whipped cream", "caramel", "extra shot", "vanilla", "cinnamon", "honey"]] | None,
        Field(description="List of extras, or empty/None for no extras"),
    ] = None,
) -> str:
    ctx.userdata.order.extras = list(extras) if extras else []
    if ctx.userdata.order.extras:
        return f"Added {', '.join(ctx.userdata.order.extras)} - making it special!"
    return "No extras - keeping it classic!"

@function_tool
async def set_name(
    ctx: RunContext[Userdata],
    name: Annotated[str, Field(description="Customer's name for the order")],
) -> str:
    ctx.userdata.order.name = name.strip().title()
    return f"Wonderful, {ctx.userdata.order.name}! Almost ready to complete your order!"

@function_tool
async def complete_order(ctx: RunContext[Userdata]) -> str:
    order = ctx.userdata.order
    
    if not order.is_complete():
        missing: list[str] = []
        if not order.drinkType: 
            missing.append("drink type")
        if not order.size: 
            missing.append("size")
        if not order.milk: 
            missing.append("milk")
        if not order.name: 
            missing.append("name")
        
        return f"Almost there! Just need: {', '.join(missing)}"
    
    try:
        save_order_to_json(order)
        extras_text = f" with {', '.join(order.extras)}" if order.extras else ""
        
        return f"Perfect! Your {order.size} {order.drinkType} with {order.milk} milk{extras_text} is confirmed, {order.name}! We're preparing your drink now - it'll be ready in 3-5 minutes! Check your order visualization file for a visual preview."
        
    except Exception as e:
        logger.error(f"Order save failed: {e}")
        return "Order recorded but there was a small issue. Don't worry, we'll make your drink right away!"

@function_tool
async def get_order_status(ctx: RunContext[Userdata]) -> str:
    order = ctx.userdata.order
    if order.is_complete():
        extras_text = f" with {', '.join(order.extras)}" if order.extras else ""
        return f"Your order is complete! {order.size} {order.drinkType} with {order.milk} milk{extras_text} for {order.name}"
    
    return "Order in progress..."

@function_tool
async def show_visualization(ctx: RunContext[Userdata]) -> str:
    """Show the HTML visualization of the current order."""
    order = ctx.userdata.order
    if not order.is_complete():
        return "Please complete your order first before viewing the visualization."
    
    try:
        html_content = generate_beverage_html(order)
        html_filename = f"current_order_{order.name}.html"
        with open(html_filename, 'w') as f:
            f.write(html_content)
        
        import webbrowser
        file_path = os.path.abspath(html_filename)
        webbrowser.open(f'file://{file_path}')
        
        return f"Opening your beverage visualization! Check your browser or look for {html_filename} in the backend folder."
    except Exception as e:
        return f"Sorry, couldn't create visualization: {e}"

class BaristaAgent(Agent):
    def __init__(self):
        super().__init__(  # type: ignore
            instructions="""You are a friendly and professional barista at Dusky Cafe.

Your mission is to take coffee orders by collecting:
- Drink Type: latte, cappuccino, americano, espresso, mocha, coffee, cold brew, matcha
- Size: small, medium, large, extra large
- Milk: whole, skim, almond, oat, soy, coconut, none
- Extras: sugar, whipped cream, caramel, extra shot, vanilla, cinnamon, honey, or none
- Customer Name: for the order

Process:
1. Greet warmly and ask for drink type
2. Ask for size preference  
3. Ask for milk choice
4. Ask about extras
5. Get customer name
6. Confirm and complete order

Be warm, enthusiastic, and professional. Ask one question at a time and confirm choices as you go.
Use the function tools to record each piece of information.""",
            tools=[
                set_drink_type,
                set_size,
                set_milk,
                set_extras,
                set_name,
                complete_order,
                get_order_status,
                show_visualization,
            ],
        )

def prewarm(proc: JobProcess) -> None:
    try:
        proc.userdata["vad"] = silero.VAD.load()
        logger.info("VAD model loaded successfully")
    except Exception as e:
        logger.error(f"Failed to load VAD model: {e}")
        raise RuntimeError(f"VAD model initialization failed: {e}") from e

async def entrypoint(ctx: JobContext) -> None:
    try:
        ctx.log_context_fields = {"room": ctx.room.name}

        session = AgentSession(  # type: ignore
            stt=deepgram.STT(model="nova-3"),
            llm=google.LLM(model="gemini-2.5-flash"),
            tts=murf.TTS(
                voice="en-US-matthew", 
                style="Conversation",
                text_pacing=True
            ),
            turn_detection=MultilingualModel(),
            vad=cast(Any, ctx.proc.userdata.get("vad")),
            preemptive_generation=True,
        )

        usage_collector = metrics.UsageCollector()

        def on_metrics_collected(ev: MetricsCollectedEvent) -> None:
            try:
                metrics.log_metrics(ev.metrics)
                usage_collector.collect(ev.metrics)
            except Exception as e:
                logger.error(f"Error processing metrics: {e}")

        session.on("metrics_collected")(on_metrics_collected)  # type: ignore

        async def log_usage() -> None:
            try:
                summary = usage_collector.get_summary()
                logger.info(f"Usage: {summary}")
            except Exception as e:
                logger.error(f"Error logging usage summary: {e}")

        ctx.add_shutdown_callback(log_usage)

        await session.start(  # type: ignore
            agent=BaristaAgent(),
            room=ctx.room,
            room_input_options=RoomInputOptions(
                noise_cancellation=noise_cancellation.BVC(),
            ),
        )
        
        # Set userdata after session start
        session.userdata = Userdata(order=OrderState())

        # Connect and wait for connection to be established
        await ctx.connect()
        
        # Wait a moment for connection to stabilize
        import asyncio
        await asyncio.sleep(0.5)
    except Exception as e:
        logger.error(f"Entrypoint failed: {e}")
        raise

if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint, prewarm_fnc=prewarm))