import logging

from dataclasses import dataclass
from pathlib import Path
import json
from datetime import datetime

from livekit.agents import Agent, function_tool, RunContext
from livekit.agents import get_job_context  # if you actually use this elsewhere



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
    # function_tool,
    # RunContext
)
from livekit.plugins import murf, silero, google, deepgram, noise_cancellation
from livekit.plugins.turn_detector.multilingual import MultilingualModel

logger = logging.getLogger("agent")

load_dotenv(".env.local")

@dataclass
class BaristaOrder:
    drinkType: str
    size: str
    milk: str
    extras: list[str]
    name: str


class Assistant(Agent):
    def __init__(self) -> None:
        super().__init__(
            instructions=(
                """You are a friendly barista at “Chai Sutta Bar”. Greet the customer and help them place a drink order.
                    Collect these fields using your tools: drinkType, size, milk, extras, name.
                    Ask one short question at a time and guide them if unsure.
                    Understand drinks like masala chai, cutting chai, ginger chai, filter coffee, cold coffee, cappuccino, iced latte.
                    Order flow: first drink type, then size, milk, extras, and finally their name.
                    Use your tools as soon as a detail is clear.
                    Keep replies brief (1 to 2 sentences) and stay fully in character.
                    When all fields are collected, confirm the final order naturally."""
            )
        )
        # internal partial state
        self._order: dict[str, object] = {}

    async def _check_completion(self) -> None:
        required = {"drinkType", "size", "milk", "extras", "name"}
        if set(self._order.keys()) == required:
            order = BaristaOrder(
                drinkType=str(self._order["drinkType"]),
                size=str(self._order["size"]),
                milk=str(self._order["milk"]),
                extras=list(self._order["extras"]),
                name=str(self._order["name"]),
            )
            await self._on_order_complete(order)
        else:
            # ask the model to continue collecting
            await self.session.generate_reply(
                instructions="Continue collecting the missing order details."
            )

    async def _on_order_complete(self, order: BaristaOrder) -> None:
        # 1) Save JSON file
        orders_dir = Path(__file__).parent.parent / "orders"
        orders_dir.mkdir(exist_ok=True)

        ts = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
        file_path = orders_dir / f"order-{ts}.json"

        data = {
            "drinkType": order.drinkType,
            "size": order.size,
            "milk": order.milk,
            "extras": order.extras,
            "name": order.name,
        }

        with file_path.open("w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

        logger.info("Saved order JSON to %s", file_path)

        # 2) Confirm to user
        base = f"Got it, {order.name}! A {order.size} {order.drinkType} with {order.milk} milk"
        if order.extras:
            extras_str = ", ".join(order.extras)
            base += f" and extras: {extras_str}."
        else:
            base += "."

        await self.session.generate_reply(
            instructions=(
                "Confirm the order in one short sentence using this summary: "
                f"'{base}'"
            )
        )

    @function_tool()
    async def set_drink_type(self, context: RunContext, drink_type: str):
        """Set the drink type, e.g. latte, cappuccino, americano, mocha, cold brew."""
        logger.info("Setting drink type to %s", drink_type)
        self._order["drinkType"] = drink_type
        await self._check_completion()

    @function_tool()
    async def set_size(self, context: RunContext, size: str):
        """Set the drink size, e.g. small, medium, large."""
        logger.info("Setting size to %s", size)
        self._order["size"] = size
        await self._check_completion()

    @function_tool()
    async def set_milk(self, context: RunContext, milk: str):
        """Set the milk type, e.g. whole, skim, oat, almond, soy."""
        logger.info("Setting milk to %s", milk)
        self._order["milk"] = milk
        await self._check_completion()

    @function_tool()
    async def add_extra(self, context: RunContext, extra: str):
        """Add an extra such as extra shot, whipped cream, syrup, etc. or would like your drink more strong."""
        logger.info("Adding extra %s", extra)
        extras = self._order.get("extras")
        if extras is None:
            extras = []
        if extra not in extras:
            extras.append(extra)
        self._order["extras"] = extras
        await self._check_completion()

    @function_tool()
    async def set_name(self, context: RunContext, name: str):
        """Set the customer's name for the order."""
        logger.info("Setting name to %s", name)
        self._order["name"] = name
        await self._check_completion()

    # To add tools, use the @function_tool decorator.
    # Here's an example that adds a simple weather tool.
    # You also have to add `from livekit.agents import function_tool, RunContext` to the top of this file
    # @function_tool
    # async def lookup_weather(self, context: RunContext, location: str):
    #     """Use this tool to look up current weather information in the given location.
    #
    #     If the location is not supported by the weather service, the tool will indicate this. You must tell the user the location's weather is unavailable.
    #
    #     Args:
    #         location: The location to look up weather information for (e.g. city name)
    #     """
    #
    #     logger.info(f"Looking up weather for {location}")
    #
    #     return "sunny with a temperature of 70 degrees."


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
