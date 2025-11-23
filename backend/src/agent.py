import logging
import json
import os
import time

from dotenv import load_dotenv
from pydantic import BaseModel

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
    RunContext,
)
from livekit.plugins import murf, silero, google, deepgram, noise_cancellation
from livekit.plugins.turn_detector.multilingual import MultilingualModel

logger = logging.getLogger("agent")

load_dotenv(".env.local")


class Assistant(Agent):
    def __init__(self) -> None:
        super().__init__(
            instructions="""
You are a friendly coffee shop barista for Blue Tokai Coffee.

The user is talking to you via voice.

Your main job:
- Help the user place a coffee order.
- Ask clear follow-up questions until you know ALL of these fields:
  - drinkType (e.g. latte, cappuccino, cold brew, americano)
  - size (small, medium, large)
  - milk (e.g. whole, skim, soy, oat, almond)
  - extras (list of extras, e.g. whipped cream, caramel, extra shot)
  - name (customer’s first name)

Behavior rules:
- Always assume the user is ordering a drink, unless they clearly say otherwise.
- Ask one or two simple questions at a time.
- If any field is missing or unclear, politely ask again or offer common options.
- Confirm the full order briefly before finalizing it.
- When you know all 5 fields and are confident, call the `save_order` tool exactly once
  with the completed order.
- After the tool returns, briefly read back the order to the customer and ask if they need anything else.

Speak naturally, like a real barista in a coffee shop. Keep responses short and conversational.
Do not use emojis or special symbols.
            """,
        )


class Order(BaseModel):
    drinkType: str
    size: str
    milk: str
    extras: list[str]
    name: str


@function_tool
async def save_order(ctx: RunContext, order: Order) -> str:
    """
    Save a completed coffee order to a JSON file and return a human-friendly summary.
    """

    # Ensure orders/ folder exists
    os.makedirs("orders", exist_ok=True)

    # Unique filename based on timestamp
    filename = f"orders/order_{int(time.time())}.json"

    # Convert Order model to dict and save as JSON
    order_dict = order.model_dump()
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(order_dict, f, indent=2, ensure_ascii=False)

    # Build a short summary for the user
    extras_text = ", ".join(order.extras) if order.extras else "no extras"
    summary = (
        f"Great, {order.name}. "
        f"I have saved your order: a {order.size} {order.drinkType} "
        f"with {order.milk} milk and {extras_text}."
    )

    logger.info(f"Saved order to {filename}: {order_dict}")

    return summary


def prewarm(proc: JobProcess):
    proc.userdata["vad"] = silero.VAD.load()


async def entrypoint(ctx: JobContext):
    # Logging setup
    ctx.log_context_fields = {
        "room": ctx.room.name,
    }

    # Voice agent session
    session = AgentSession(
        # Speech-to-text
        stt=deepgram.STT(model="nova-3"),
        # LLM
        llm=google.LLM(
            model="gemini-2.5-flash",
        ),
        # Text-to-speech (Murf Falcon voice)
        tts=murf.TTS(
            voice="en-US-matthew",
            style="Conversation",
            tokenizer=tokenize.basic.SentenceTokenizer(min_sentence_len=2),
            text_pacing=True,
        ),
        # Turn detection and VAD
        turn_detection=MultilingualModel(),
        vad=ctx.proc.userdata["vad"],
        # Allow preemptive responses
        preemptive_generation=True,
        # Tools available to the LLM
        tools=[save_order],
    )

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

    # Start the voice session
    await session.start(
        agent=Assistant(),
        room=ctx.room,
        room_input_options=RoomInputOptions(
            noise_cancellation=noise_cancellation.BVC(),
        ),
    )

    # Join the room and connect to the user
    await ctx.connect()


if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint, prewarm_fnc=prewarm))
