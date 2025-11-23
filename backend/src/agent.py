import logging

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
You are a friendly barista at Falcon Coffee Shop.

Your job:
1. Greet customers warmly.
2. Take coffee orders (e.g., latte, cappuccino, americano, espresso, cold brew, mocha).
3. Ask follow-up questions until you know ALL of these:
   - drink type
   - size (small/medium/large)
   - milk type
   - sugar level
4. AFTER you have all four details, you MUST call the `place_order` tool to calculate the bill.
5. Never guess the price yourself. Always rely on the `place_order` tool.
6. After the tool returns, clearly tell the user:
   - their full order
   - the total bill amount in rupees
   - a friendly closing message.

Tone:
- Warm, friendly, welcoming.
- Example phrases: "Hey there!", "What can I get started for you today?"
- Keep answers short and natural like a real barista.
"""
        )

    # ------------- Coffee Order Tool (used by the LLM) -------------
    @function_tool()
    async def place_order(
        self,
        context: RunContext,
        item: str,
        size: str,
        milk: str,
        sugar: str,
    ) -> str:
        """
        Takes a coffee order and returns the final price.

        Args:
            item: Coffee type (latte, cappuccino, americano, espresso, mocha, cold brew)
            size: small / medium / large
            milk: milk type (e.g. regular, oat, almond, soy)
            sugar: sugar preference (e.g. less, normal, extra)
        """
        prices = {
            "latte": 120,
            "cappuccino": 130,
            "americano": 100,
            "espresso": 90,
            "mocha": 150,
            "cold brew": 160,
        }
        size_extra = {"small": 0, "medium": 20, "large": 40}

        base_price = prices.get(item.lower(), 120)
        total_price = base_price + size_extra.get(size.lower(), 0)

        logger.info(
            f"Placing order: item={item}, size={size}, milk={milk}, sugar={sugar}, total={total_price}"
        )

        return (
            f"Order confirmed: {size} {item} with {milk} milk and {sugar} sugar. "
            f"Your total bill is ₹{total_price}."
        )


# ----------------------- Session Setup -----------------------
def prewarm(proc: JobProcess):
    proc.userdata["vad"] = silero.VAD.load()


async def entrypoint(ctx: JobContext):
    ctx.log_context_fields = {"room": ctx.room.name}

    session = AgentSession(
        stt=deepgram.STT(model="nova-3"),
        llm=google.LLM(model="gemini-2.5-flash"),
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
        room_input_options=RoomInputOptions(
            noise_cancellation=noise_cancellation.BVC(),
        ),
    )

    await ctx.connect()


if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint, prewarm_fnc=prewarm))
