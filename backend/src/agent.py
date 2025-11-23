import logging
import json
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


class Assistant(Agent):
    def __init__(self) -> None:
        super().__init__(
            instructions="""You are a friendly Coffee Shop Barista for a premium coffee brand.
            Your goal is to take the customer's beverage order efficiently and warmly.
            
            You must collect the following details to complete an order:
            1. Drink Type (e.g., Latte, Cappuccino, Americano)
            2. Size (e.g., Small, Medium, Large)
            3. Milk Preference (e.g., Whole, Oat, Almond, Soy)
            4. Customer Name (for the cup)
            
            You can also add Extras (e.g., extra shot, sugar, syrup) if requested.

            Behavior:
            - Ask short, conversational questions.
            - Ask for missing details one at a time. Do not overwhelm the user.
            - If the user provides multiple details at once, update them all.
            - Gently redirect if the user goes off-topic.
            - Once all required fields (drinkType, size, milk, name) are present, confirm the order summary with the user.
            - After the user confirms, IMMEDIATELY call the `submit_order` tool.
            - Be friendly and polite.
            """,
        )
        self.order = {
            "drinkType": "",
            "size": "",
            "milk": "",
            "extras": [],
            "name": ""
        }

    @function_tool
    async def update_order(
        self, 
        context: RunContext, 
        drink_type: Optional[str] = None, 
        size: Optional[str] = None, 
        milk: Optional[str] = None, 
        extras: Optional[List[str]] = None, 
        name: Optional[str] = None
    ):
        """Update the current order with new details provided by the user.
        
        Args:
            drink_type: The type of beverage (e.g., "Latte", "Cappuccino").
            size: The size of the drink (e.g., "Small", "Medium", "Large").
            milk: The type of milk (e.g., "Oat", "Whole", "Almond").
            extras: A list of any extra additions (e.g., ["sugar", "extra hot"]).
            name: The customer's name.
        """
        if drink_type:
            self.order["drinkType"] = drink_type
        if size:
            self.order["size"] = size
        if milk:
            self.order["milk"] = milk
        if extras:
            # Append new extras to existing ones, or replace? 
            # Usually adding is safer, but let's just extend the list if it exists
            current_extras = self.order.get("extras", [])
            if isinstance(extras, list):
                current_extras.extend(extras)
            else:
                current_extras.append(extras)
            self.order["extras"] = current_extras
        if name:
            self.order["name"] = name
        
        logger.info(f"Order updated: {self.order}")
        return f"Order updated. Current state: {json.dumps(self.order)}"

    @function_tool
    async def submit_order(self, context: RunContext):
        """Finalize and save the order to a file. Call this ONLY when all required fields (drinkType, size, milk, name) are filled and confirmed."""
        
        # Validation check (optional, but good for robustness)
        missing = []
        if not self.order["drinkType"]: missing.append("drink type")
        if not self.order["size"]: missing.append("size")
        if not self.order["milk"]: missing.append("milk")
        if not self.order["name"]: missing.append("name")
        
        if missing:
            return f"Cannot submit order yet. Missing details: {', '.join(missing)}. Please ask the user for these."

        file_path = "order.json"
        try:
            with open(file_path, "w") as f:
                json.dump(self.order, f, indent=2)
            logger.info(f"Order saved to {file_path}")
            return "Order successfully saved to order.json. Tell the user their order is confirmed!"
        except Exception as e:
            logger.error(f"Failed to save order: {e}")
            return f"Error saving order: {e}"


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

