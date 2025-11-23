import logging
import json
from dataclasses import dataclass, asdict, field
from typing import List, Optional

from dotenv import load_dotenv
from livekit.agents import (
    Agent,
    AgentSession,
    JobContext,
    JobProcess,
    MetricsCollectedEvent,
    RoomInputOptions,
    WorkerOptions,
    cli,
    metrics,
    tokenize,
    function_tool,
    RunContext
)
from livekit.plugins import murf, silero, google, deepgram, noise_cancellation
from livekit.plugins.turn_detector.multilingual import MultilingualModel

logger = logging.getLogger("agent")

load_dotenv(".env.local")

# --- 1. DEFINE ORDER STATE ---
@dataclass
class CoffeeOrder:
    """The state object for the user's coffee order."""
    drinkType: Optional[str] = None
    size: Optional[str] = None
    milk: Optional[str] = None
    extras: List[str] = field(default_factory=list)
    name: Optional[str] = None

    def is_complete(self) -> bool:
        """Checks if all required fields are filled."""
        return all([self.drinkType, self.size, self.milk, self.name])
    
    def to_json_file(self) -> str:
        """Writes the complete order to a JSON file."""
        name_part = self.name.replace(' ', '_') if self.name else "unknown"
        filename = f"order_{name_part}.json"
        
        order_data = asdict(self)
        
        with open(filename, 'w') as f:
            json.dump(order_data, indent=4, fp=f)
        
        logger.info(f"Order saved to {filename}")
        return filename

# --- 2. DEFINE THE BARISTA TOOL ---
@function_tool
async def take_order(
    context: RunContext,
    drinkType: Optional[str] = None,
    size: Optional[str] = None,
    milk: Optional[str] = None,
    extras: Optional[List[str]] = None,
    name: Optional[str] = None,
) -> str:
    """
    Called when the user is placing or modifying a coffee order. 
    Use this tool to update the order state with information provided by the customer.
    
    Args:
        drinkType: The type of coffee (e.g., latte, cappuccino, espresso, americano).
        size: The size of the drink (small, medium, or large).
        milk: The type of milk (whole, skim, oat, almond, soy).
        extras: Additional items like whipped cream, extra shot, vanilla syrup, caramel.
        name: The customer's name for the order.
    """
    
    # Access the shared state object
    order: CoffeeOrder = context.userdata["order"]
    
    # Update the order state with any provided arguments
    if drinkType is not None:
        order.drinkType = drinkType
    if size is not None:
        order.size = size
    if milk is not None:
        order.milk = milk
    if extras is not None:
        order.extras = extras if extras else []
    if name is not None:
        order.name = name

    # Check if order is complete
    if order.is_complete():
        # Save the order
        filename = order.to_json_file()
        
        # Send order data to frontend (Advanced Challenge)
        try:
            await context.room.local_participant.publish_data(
                json.dumps({
                    "type": "ORDER_COMPLETE",
                    "order": asdict(order)
                }).encode('utf-8'),
                topic="order_state"
            )
            logger.info("Order data sent to frontend")
        except Exception as e:
            logger.error(f"Failed to send order data: {e}")
        
        total = 4.50 + len(order.extras) * 0.50
        return (
            f"ORDER COMPLETE! The order has been saved to {filename}. "
            f"Confirm with enthusiasm: '{order.size} {order.drinkType} with {order.milk} milk"
            f"{', with ' + ', '.join(order.extras) if order.extras else ''}. "
            f"Order for {order.name}. Your total is ${total:.2f}. Thank you for choosing CodeBrew Coffee!'"
        )
    
    # Identify missing fields
    missing_fields = []
    if not order.drinkType:
        missing_fields.append("drink type")
    if not order.size:
        missing_fields.append("size")
    if not order.milk:
        missing_fields.append("milk type")
    if not order.name:
        missing_fields.append("name for the order")
    
    return (
        f"ORDER PENDING. Still need: {', '.join(missing_fields)}. "
        f"Ask the customer for the next missing item in a friendly, conversational way."
    )

# --- 3. DEFINE THE BARISTA AGENT ---
class BaristaAgent(Agent):
    def __init__(self, llm) -> None:
        super().__init__(
            instructions=(
                "You are A.Y. Ushi, a friendly and enthusiastic barista at CodeBrew Coffee. "
                "Your goal is to take complete coffee orders from customers. "
                "\n\n"
                "GREETING: Start every new conversation with: 'Welcome to CodeBrew Coffee! I'm A.Y. Ushi. What can I get started for you today?'"
                "\n\n"
                "IMPORTANT RULES:\n"
                "- Call the take_order tool IMMEDIATELY after the customer provides ANY order information\n"
                "- Ask for ONE piece of missing information at a time\n"
                "- Be conversational and friendly, not robotic\n"
                "- If the customer mentions multiple things at once, call take_order with all of them\n"
                "- Once the order is complete, enthusiastically confirm all details and the total\n"
                "\n"
                "Example flow:\n"
                "Customer: 'I'd like a latte'\n"
                "You: [calls take_order with drinkType='latte'] 'Great choice! What size would you like - small, medium, or large?'\n"
                "\n"
                "Keep responses brief and natural. You're a barista, not a robot!"
            ),
            tools=[take_order],
            llm=llm
        )


def prewarm(proc: JobProcess):
    proc.userdata["vad"] = silero.VAD.load()


async def entrypoint(ctx: JobContext):
    # Set up the initial state for the session
    initial_order = CoffeeOrder()
    
    # Logging setup
    ctx.log_context_fields = {
        "room": ctx.room.name,
    }

    # Create the LLM once
    llm = google.LLM(model="gemini-2.5-flash")

    # Set up a voice AI pipeline
    session = AgentSession(
        stt=deepgram.STT(model="nova-3"),
        llm=llm,
        tts=murf.TTS(
            voice="en-US-matthew", 
            style="Conversation",
            tokenizer=tokenize.basic.SentenceTokenizer(min_sentence_len=2),
            text_pacing=True
        ),
        turn_detection=MultilingualModel(),
        vad=ctx.proc.userdata["vad"],
        preemptive_generation=True,
    )
    
    # Store order in session userdata
    session.userdata = {"order": initial_order}

    # Metrics collection
    usage_collector = metrics.UsageCollector()

    @session.on("metrics_collected")
    def _on_metrics_collected(ev: MetricsCollectedEvent):
        metrics.log_metrics(ev.metrics)
        usage_collector.collect(ev.metrics)

    async def log_usage():
        summary = usage_collector.get_summary()
        logger.info(f"Usage: {summary}")

    ctx.add_shutdown_callback(log_usage)

    # Start the session
    await session.start(
        agent=BaristaAgent(llm=llm),
        room=ctx.room,
        room_input_options=RoomInputOptions(
            noise_cancellation=noise_cancellation.BVC(),
        ),
    )

    # Join the room and connect
    await ctx.connect()


if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint, prewarm_fnc=prewarm))