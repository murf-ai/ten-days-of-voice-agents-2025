import json
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
)
from livekit.plugins import murf, deepgram, noise_cancellation, google, silero
from livekit.plugins.turn_detector.multilingual import MultilingualModel

logger = logging.getLogger("agent")
load_dotenv(".env.local")

# ---------------------------
# Coffee Order State
# ---------------------------
order = {
    "drinkType": "",
    "size": "",
    "milk": "",
    "extras": [],
    "name": ""
}

questions = {
    "drinkType": "Which drink would you like? Latte, Cappuccino, Americano, or something else?",
    "size": "What size would you like? Small, Medium, or Large?",
    "milk": "Which type of milk do you prefer? Whole, Skim, Almond, or Oat?",
    "extras": "Any extras like whipped cream or syrup? (You can list multiple separated by commas)",
    "name": "May I have your name for the order?"
}

# ---------------------------
# Load VAD on main thread
# ---------------------------
vad_model = silero.VAD.load()

def prewarm(proc: JobProcess):
    proc.userdata["vad"] = vad_model

# ---------------------------
# Barista Agent
# ---------------------------
class CoffeeBarista(Agent):
    def __init__(self):
        super().__init__(
            instructions="""You are a friendly coffee shop barista.
            Ask the customer about their order and take note of the drink type, size, milk preference, extras, and name.
            Speak politely, ask clarifying questions, and save the completed order to a JSON file."""
        )

    async def on_join(self, context):
        # Ask the first incomplete question when user joins
        for field in order:
            if not order[field]:
                await context.send_speech(questions[field])
                break

    async def on_user_message(self, message, context):
        # Fill incomplete fields one by one
        for field in order:
            if not order[field]:
                response = message.text.strip()
                if field == "extras":
                    order[field] = [e.strip() for e in response.split(",") if e.strip()]
                else:
                    order[field] = response

                # Ask next question
                for next_field in order:
                    if not order[next_field]:
                        await context.send_speech(questions[next_field])
                        return

                # All fields completed
                summary = "\n".join([f"{k}: {v}" for k, v in order.items()])
                await context.send_speech(f"Thank you! Here is your order summary:\n{summary}")
                save_order()
                return

# ---------------------------
# Save Order
# ---------------------------
def save_order():
    filename = f"{order['name']}_order.json"
    with open(filename, "w") as f:
        json.dump(order, f, indent=4)
    logger.info(f"Order saved as {filename}")

# ---------------------------
# Entrypoint
# ---------------------------
async def entrypoint(ctx: JobContext):
    ctx.log_context_fields = {"room": ctx.room.name}

    # Create a session with an actual LLM for TTS
    session = AgentSession(
        stt=deepgram.STT(model="nova-3"),
        llm=google.LLM(model="gemini-2.5-flash"),  # <-- needed for TTS
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

    usage_collector = metrics.UsageCollector()

    @session.on("metrics_collected")
    def _on_metrics_collected(ev: MetricsCollectedEvent):
        metrics.log_metrics(ev.metrics)
        usage_collector.collect(ev.metrics)

    async def log_usage():
        summary = usage_collector.get_summary()
        logger.info(f"Usage: {summary}")

    ctx.add_shutdown_callback(log_usage)

    # Start session with CoffeeBarista agent
    await session.start(
        agent=CoffeeBarista(),
        room=ctx.room,
        room_input_options=RoomInputOptions(
            noise_cancellation=noise_cancellation.BVC(),
        ),
    )

    await ctx.connect()

# ---------------------------
# Run Agent
# ---------------------------
if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint, prewarm_fnc=prewarm))
