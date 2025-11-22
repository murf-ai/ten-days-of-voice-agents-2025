import logging
import json
from datetime import datetime
from pathlib import Path

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
from livekit.plugins import murf, silero, google, deepgram, assemblyai, noise_cancellation
from livekit.plugins.turn_detector.multilingual import MultilingualModel

logger = logging.getLogger("agent")

load_dotenv(".env.local")


class CoffeeBaristaAgent(Agent):
    def __init__(self, room=None) -> None:
        super().__init__(
            instructions="""You are a friendly barista at Cafe Latte Coffee Shop. The user is interacting with you via voice to place a coffee order.
            Welcome The user First
            Your job is to take their complete order by collecting:
            - drinkType: The type of drink (e.g., latte, cappuccino, americano, espresso, mocha, cold brew)
            - size: Small, medium, or large
            - milk: Type of milk (whole, skim, oat, almond, soy, or none)
            - extras: Any extras like whipped cream, extra shot, vanilla syrup, caramel drizzle, etc.
            - name: Customer's name for the order
            
            Be conversational and friendly. Ask clarifying questions one at a time if information is missing.
            Once you have ALL the information, use the save_order tool to save the order.
            After saving, confirm the order and thank the customer.
            
            Keep responses brief and natural. Speak like a real barista would.""",
        )
        self._room = room

    @function_tool
    async def save_order(
        self,
        context: RunContext,
        drink_type: str,
        size: str,
        milk: str,
        extras: str,
        name: str
    ):
        """Save the complete coffee order to a JSON file and send to frontend.
        
        Args:
            drink_type: Type of drink (e.g., latte, cappuccino, americano)
            size: Size of drink (small, medium, large)
            milk: Type of milk (whole, skim, oat, almond, soy, none)
            extras: Comma-separated list of extras (e.g., whipped cream, extra shot, vanilla syrup)
            name: Customer's name for the order
        """
        logger.info(f"Saving order for {name}: {size} {drink_type} with {milk} milk")
        
        # Parse extras into a list
        extras_list = [e.strip() for e in extras.split(",")] if extras else []
        
        # Create order object
        order = {
            "drinkType": drink_type,
            "size": size,
            "milk": milk,
            "extras": extras_list,
            "name": name,
            "timestamp": datetime.now().isoformat()
        }
        
        # Create orders directory if it doesn't exist
        orders_dir = Path("orders")
        orders_dir.mkdir(exist_ok=True)
        
        # Save order to JSON file
        filename = f"order_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{name.replace(' ', '_')}.json"
        filepath = orders_dir / filename
        
        with open(filepath, "w") as f:
            json.dump(order, f, indent=2)
        
        logger.info(f"Order saved to {filepath}")
        
        # Send order to frontend via data channel
        try:
            if self._room:
                await self._room.local_participant.publish_data(
                    json.dumps(order).encode('utf-8'),
                    topic="order-updates"
                )
                logger.info("Order sent to frontend")
            else:
                logger.warning("Room not available, cannot send order to frontend")
        except Exception as e:
            logger.error(f"Failed to send order to frontend: {e}")
        
        return f"Order saved successfully! Your {size} {drink_type} will be ready soon, {name}!"


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
<<<<<<< HEAD
                style="Conversation"
=======
                style="Conversation",
                tokenizer=tokenize.basic.SentenceTokenizer(min_sentence_len=1),
                text_pacing=True
>>>>>>> 22b3026 (day1)
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
        agent=CoffeeBaristaAgent(room=ctx.room),
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
