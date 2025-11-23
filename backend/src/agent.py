import logging
import json
from pathlib import Path
from typing import List

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

# -----------------------------
# Coffee Order Model (Day 2)
# -----------------------------


class OrderState(BaseModel):
    drinkType: str
    size: str
    milk: str
    extras: List[str]
    name: str


# File where orders will be saved
ORDERS_FILE = Path(__file__).parent / "orders.json"

``
@function_tool()
async def submit_order(
    context: RunContext,
    drinkType: str,
    size: str,
    milk: str,
    extras: List[str],
    name: str,
) -> str:
    """
    Save the completed coffee order to a JSON file.
    Called ONLY when all fields are known.
    """

    # Build OrderState object
    order = OrderState(
        drinkType=drinkType,
        size=size,
        milk=milk,
        extras=extras,
        name=name,
    )

    order_dict = order.model_dump()

    # Load existing orders (if file exists)
    if ORDERS_FILE.exists():
        try:
            existing = json.loads(ORDERS_FILE.read_text())
            if not isinstance(existing, list):
                existing = []
        except Exception:
            existing = []
    else:
        existing = []

    # Append new order
    existing.append(order_dict)

    # Save back to file with pretty formatting
    ORDERS_FILE.write_text(json.dumps(existing, indent=2))

    # Short message back to LLM if it wants to use it
    return f"Order saved for {name}"


class Assistant(Agent):
    def __init__(self) -> None:
        super().__init__(
            instructions="""
You are a friendly barista at Aurora Coffee.

The user is speaking to you via voice, but you see it as text. Your job is to take coffee orders and keep things simple and warm.

You must build a coffee order with these fields:
- drinkType: the main drink, for example: latte, cappuccino, cold brew, americano, mocha.
- size: small, medium, or large.
- milk: for example: regular, skim, soy, almond, oat.
- extras: a list of extras, for example: extra shot, sugar, vanilla syrup, caramel drizzle, whipped cream, decaf, ice. If there are no extras, use an empty list.
- name: the customer's name for the cup.

Conversation rules:
1) Start by greeting the customer and asking what they would like to drink.
2) Ask short follow-up questions until you know all of: drinkType, size, milk, extras, and name.
3) Ask only one clarifying question at a time and keep questions very clear.
4) When you know all fields, call the submit_order tool with drinkType, size, milk, extras (as a list of strings), and name.
5) After the tool call, say a brief spoken confirmation, for example:
   "Got it, Sahil. One large oat milk latte with an extra shot."
6) Then politely ask if they would like anything else.

Important:
- Do not call submit_order until every field is clearly known.
- If any field is missing or unclear, ask another question instead of guessing.
- Keep your spoken responses concise and without emojis or special symbols.
""",
            tools=[submit_order],
        )


def prewarm(proc: JobProcess):
    proc.userdata["vad"] = silero.VAD.load()


async def entrypoint(ctx: JobContext):
    # Logging setup
    ctx.log_context_fields = {
        "room": ctx.room.name,
    }

    session = AgentSession(
        stt=deepgram.STT(model="nova-3"),
        llm=google.LLM(
            model="gemini-2.5-flash",
        ),
        tts=murf.TTS(
            voice="en-US-matthew",
            style="Conversation",
            tokenizer=tokenize.basic.SentenceTokenizer(min_sentence_len=2),
            text_pacing=True,
        ),
        turn_detection=MultilingualModel(),
        vad=ctx.proc.userdata["vad"],
        preemptive_generation=True,
    )

    usage_collector = metrics.UsageCollector()

    @session.on("metrics_collected")
    def _on_metrics_collected(ev: MetricsCollectedEvent):
        metrics.log_metrics(ev.metrics)
        usage_collector.collect(ev.metrics)

    async def log_usage():
        summary = usage_collector.get_summary()
        logger.info(f"Usage: {summary}")

    ctx.add_shutdown_callback(log_usage)

    await session.start(
        agent=Assistant(),
        room=ctx.room,
        room_input_options=RoomInputOptions(),
    )

    await ctx.connect()


if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint, prewarm_fnc=prewarm))
