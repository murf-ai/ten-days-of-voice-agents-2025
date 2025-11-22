import logging
import json
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
from livekit.plugins import murf, silero, google, deepgram, noise_cancellation
from livekit.plugins.turn_detector.multilingual import MultilingualModel

logger = logging.getLogger("agent")
load_dotenv(".env.local")

# ----------------------------
# Global Order State
# ----------------------------
order_state = {
    "drinkType": "",
    "size": "",
    "milk": "",
    "extras": [],
    "name": ""
}

# ----------------------------
# Helper Functions
# ----------------------------
def get_next_question(order):
    if not order["drinkType"]:
        return "What would you like to drink today? (latte, espresso, cappuccino)"
    if not order["size"]:
        return "What size would you like? (small, medium, large)"
    if not order["milk"]:
        return "Which milk would you like? (whole, skim, oat)"
    if not order["extras"]:
        return "Any extras? (whipped cream, caramel, chocolate, or none)"
    if not order["name"]:
        return "May I have your name for the order?"
    return None  # All fields filled

def save_order(order):
    with open("order_summary.json", "w") as f:
        json.dump(order, f, indent=2)

# ----------------------------
# Assistant Agent
# ----------------------------
class Assistant(Agent):
    def __init__(self) -> None:
        super().__init__(
            instructions="""You are a helpful voice AI assistant. The user is interacting with you via voice, even if you perceive the conversation as text.
            You eagerly assist users with their questions by providing information from your extensive knowledge.
            Your responses are concise, to the point, and without any complex formatting or punctuation including emojis, asterisks, or other symbols.
            You are curious, friendly, and have a sense of humor."""
        )

    async def handle_order(self, user_text: str):
        text = user_text.lower()

        # ----------------------------
        # Fill order_state fields
        # ----------------------------
        if not order_state["drinkType"]:
            order_state["drinkType"] = text
        elif not order_state["size"]:
            order_state["size"] = text
        elif not order_state["milk"]:
            order_state["milk"] = text
        elif not order_state["extras"]:
            if "none" in text:
                order_state["extras"] = []
            else:
                order_state["extras"] = [x.strip() for x in text.split(",")]
        elif not order_state["name"]:
            order_state["name"] = text

        # ----------------------------
        # Decide next question or complete
        # ----------------------------
        next_question = get_next_question(order_state)
        if next_question is None:
            save_order(order_state)
            response_text = f"Thanks {order_state['name']}! Your {order_state['size']} {order_state['drinkType']} with {', '.join(order_state['extras']) or 'no extras'} is ready."
        else:
            response_text = next_question

        # Convert text to speech
        audio_url = self.tts.speak(response_text)
        return response_text, audio_url

# ----------------------------
# Prewarm
# ----------------------------
def prewarm(proc: JobProcess):
    proc.userdata["vad"] = silero.VAD.load()

# ----------------------------
# Entry Point
# ----------------------------
async def entrypoint(ctx: JobContext):
    # Logging setup
    ctx.log_context_fields = {
        "room": ctx.room.name,
    }

    # ----------------------------
    # Setup Voice AI Pipeline
    # ----------------------------
    session = AgentSession(
        stt=deepgram.STT(model="nova-3"),
        llm=google.LLM(model="gemini-2.5-flash"),
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

    # ----------------------------
    # Metrics Collection
    # ----------------------------
    usage_collector = metrics.UsageCollector()

    @session.on("metrics_collected")
    def _on_metrics_collected(ev: MetricsCollectedEvent):
        metrics.log_metrics(ev.metrics)
        usage_collector.collect(ev.metrics)

    async def log_usage():
        summary = usage_collector.get_summary()
        logger.info(f"Usage: {summary}")

    ctx.add_shutdown_callback(log_usage)

    # ----------------------------
    # Start the session
    # ----------------------------
    await session.start(
        agent=Assistant(),
        room=ctx.room,
        room_input_options=RoomInputOptions(
            noise_cancellation=noise_cancellation.BVC(),
        ),
    )

    # ----------------------------
    # Handle User Messages
    # ----------------------------
    @session.on("message")
    async def on_user_message(message):
        user_text = message.text
        assistant: Assistant = session.agent
        response_text, audio_url = await assistant.handle_order(user_text)
        await session.send_text(response_text)
        await session.send_audio(audio_url)

    # Connect to the room
    await ctx.connect()

# ----------------------------
# Run CLI
# ----------------------------
if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint, prewarm_fnc=prewarm))
