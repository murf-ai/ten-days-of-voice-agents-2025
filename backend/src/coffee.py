import logging
import json
import os
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from livekit.agents import ( #type: ignore
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
from livekit.plugins import murf, silero, google, deepgram, noise_cancellation #type: ignore
from livekit.plugins.turn_detector.multilingual import MultilingualModel #type: ignore

logger = logging.getLogger("agent")

load_dotenv(".env")


class Assistant(Agent):
    def __init__(self) -> None:
        super().__init__(
            instructions="""You are a friendly and enthusiastic barista working at Imaginary Coffee Co., the finest coffee shop in town. 
            You're passionate about coffee and love helping customers find their perfect drink.
            Your goal is to take complete coffee orders by collecting all required information:
            - Drink type (Latte, Cappuccino, Americano, Espresso, Macchiato, Mocha, Cold Brew, etc.)
            - Size (Small, Medium, Large)
            - Milk preference (Whole, 2%, Oat, Almond, Soy, Coconut, or None)
            - Any extras (Extra shot, Decaf, Sugar, Honey, Whipped cream, Vanilla syrup, Caramel syrup, etc.)
            - Customer's name
            
            Be conversational and ask clarifying questions until you have all the information needed.
            When the order is complete, confirm all details with the customer before finalizing it.
            Keep responses natural, friendly, and concise. No complex formatting or symbols.""",
        )
        
        # Initialize order state
        self.order_state = {
            "drinkType": None,
            "size": None,
            "milk": None,
            "extras": [],
            "name": None
        }
        
        # Create orders directory if it doesn't exist
        self.orders_dir = Path("orders")
        self.orders_dir.mkdir(exist_ok=True)

    @function_tool
    async def update_order(self, context: RunContext, drink_type: str = None, size: str = None, 
                          milk: str = None, extras: str = None, name: str = None):
        """Update the customer's coffee order with new information.
        
        Use this tool whenever the customer provides information about their order.
        You can update multiple fields at once or just one field at a time.
        
        Args:
            drink_type: Type of coffee drink (e.g., Latte, Cappuccino, Americano, Espresso, Macchiato, Mocha, Cold Brew)
            size: Size of the drink (Small, Medium, Large)
            milk: Type of milk (Whole, 2%, Oat, Almond, Soy, Coconut, None)
            extras: Any extras as a comma-separated string (e.g., "Extra shot, Vanilla syrup")
            name: Customer's name
        """
        
        logger.info(f"Updating order: drink_type={drink_type}, size={size}, milk={milk}, extras={extras}, name={name}")
        
        # Update order state
        if drink_type:
            self.order_state["drinkType"] = drink_type.strip()
        if size:
            self.order_state["size"] = size.strip()
        if milk:
            self.order_state["milk"] = milk.strip()
        if extras:
            # Parse extras and add to list
            new_extras = [extra.strip() for extra in extras.split(",") if extra.strip()]
            self.order_state["extras"].extend(new_extras)
            # Remove duplicates while preserving order
            self.order_state["extras"] = list(dict.fromkeys(self.order_state["extras"]))
        if name:
            self.order_state["name"] = name.strip()
            
        # Check what's still missing
        missing_fields = []
        if not self.order_state["drinkType"]:
            missing_fields.append("drink type")
        if not self.order_state["size"]:
            missing_fields.append("size")
        if not self.order_state["milk"]:
            missing_fields.append("milk preference")
        if not self.order_state["name"]:
            missing_fields.append("name")
            
        current_order = f"Current order: {self.order_state['drinkType'] or 'TBD'} ({self.order_state['size'] or 'TBD'})"
        if self.order_state['milk']:
            current_order += f" with {self.order_state['milk']} milk"
        if self.order_state['extras']:
            current_order += f", extras: {', '.join(self.order_state['extras'])}"
        if self.order_state['name']:
            current_order += f" for {self.order_state['name']}"
            
        if missing_fields:
            return f"Got it! {current_order}. Still need: {', '.join(missing_fields)}."
        else:
            return f"Perfect! {current_order}. Order is complete and ready to finalize!"
    
    @function_tool
    async def finalize_order(self, context: RunContext):
        """Finalize and save the customer's complete order to a JSON file.
        
        Only use this tool when all required fields are filled and customer confirms the order.
        """
        
        # Check if order is complete
        required_fields = ["drinkType", "size", "milk", "name"]
        missing_fields = [field for field in required_fields if not self.order_state[field]]
        
        if missing_fields:
            return f"Cannot finalize order. Missing: {', '.join(missing_fields)}. Please collect this information first."
        
        # Create order with timestamp
        final_order = {
            "orderId": f"IMAGINE_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            "timestamp": datetime.now().isoformat(),
            "customerName": self.order_state["name"],
            "drinkType": self.order_state["drinkType"],
            "size": self.order_state["size"],
            "milk": self.order_state["milk"],
            "extras": self.order_state["extras"],
            "status": "ordered",
            "location": "Imaginary Coffee Co."
        }
        
        # Save order to JSON file
        filename = f"order_{final_order['orderId']}.json"
        filepath = self.orders_dir / filename
        
        try:
            with open(filepath, 'w') as f:
                json.dump(final_order, f, indent=2)
            
            logger.info(f"Order saved to {filepath}")
            
            # Reset order state for next customer
            self.order_state = {
                "drinkType": None,
                "size": None, 
                "milk": None,
                "extras": [],
                "name": None
            }
            
            order_summary = f"{final_order['size']} {final_order['drinkType']}"
            if final_order['milk'] != "None":
                order_summary += f" with {final_order['milk']} milk"
            if final_order['extras']:
                order_summary += f" and {', '.join(final_order['extras'])}"
            order_summary += f" for {final_order['customerName']}"
            
            return f"Order finalized! {order_summary}. Order ID: {final_order['orderId']}. Thank you for choosing Imaginary Coffee Co.!"
            
        except Exception as e:
            logger.error(f"Failed to save order: {e}")
            return f"Order completed but there was an issue saving it. Please contact a manager. Order details: {self.order_state}"


def prewarm(proc: JobProcess):
    proc.userdata["vad"] = silero.VAD.load()


async def entrypoint(ctx: JobContext):
    # Logging setup
    # Add any other context you want in all log entries here
    ctx.log_context_fields = {
        "room": ctx.room.name,
    }

    # Set up a voice AI pipeline using OpenAI, Cartesia, AssemblyAI, and the LiveKit turn detector
    session = AgentSession(
        # Speech-to-text (STT) is your agent's ears, turning the user's speech into text that the LLM can understand
        # See all available models at https://docs.livekit.io/agents/models/stt/
        stt=deepgram.STT(model="nova-3"),
        # A Large Language Model (LLM) is your agent's brain, processing user input and generating a response
        # See all available models at https://docs.livekit.io/agents/models/llm/
        llm=google.LLM(
                model="gemini-2.5-flash",
            ),
        # Text-to-speech (TTS) is your agent's voice, turning the LLM's text into speech that the user can hear
        # See all available models as well as voice selections at https://docs.livekit.io/agents/models/tts/
        tts=murf.TTS(
                voice="en-US-matthew", 
                style="Conversation",
                tokenizer=tokenize.basic.SentenceTokenizer(min_sentence_len=2),
                text_pacing=True
            ),
        # VAD and turn detection are used to determine when the user is speaking and when the agent should respond
        # See more at https://docs.livekit.io/agents/build/turns
        turn_detection=MultilingualModel(),
        vad=ctx.proc.userdata["vad"],
        # allow the LLM to generate a response while waiting for the end of turn
        # See more at https://docs.livekit.io/agents/build/audio/#preemptive-generation
        preemptive_generation=True,
    )

    # To use a realtime model instead of a voice pipeline, use the following session setup instead.
    # (Note: This is for the OpenAI Realtime API. For other providers, see https://docs.livekit.io/agents/models/realtime/))
    # 1. Install livekit-agents[openai]
    # 2. Set OPENAI_API_KEY in .env.local
    # 3. Add `from livekit.plugins import openai` to the top of this file
    # 4. Use the following session setup instead of the version above
    # session = AgentSession(
    #     llm=openai.realtime.RealtimeModel(voice="marin")
    # )

    # Metrics collection, to measure pipeline performance
    # For more information, see https://docs.livekit.io/agents/build/metrics/
    usage_collector = metrics.UsageCollector()

    @session.on("metrics_collected")
    def _on_metrics_collected(ev: MetricsCollectedEvent):
        metrics.log_metrics(ev.metrics)
        usage_collector.collect(ev.metrics)

    async def log_usage():
        summary = usage_collector.get_summary()
        logger.info(f"Usage: {summary}")

    ctx.add_shutdown_callback(log_usage)

    # # Add a virtual avatar to the session, if desired
    # # For other providers, see https://docs.livekit.io/agents/models/avatar/
    # avatar = hedra.AvatarSession(
    #   avatar_id="...",  # See https://docs.livekit.io/agents/models/avatar/plugins/hedra
    # )
    # # Start the avatar and wait for it to join
    # await avatar.start(session, room=ctx.room)

    # Start the session, which initializes the voice pipeline and warms up the models
    await session.start(
        agent=Assistant(),
        room=ctx.room,
        room_input_options=RoomInputOptions(
            # For telephony applications, use `BVCTelephony` for best results
            noise_cancellation=noise_cancellation.BVC(),
        ),
    )

    # Join the room and connect to the user
    await ctx.connect()


if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint, prewarm_fnc=prewarm))
