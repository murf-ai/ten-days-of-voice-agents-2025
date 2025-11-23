import logging
import json
from dataclasses import dataclass, field
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
    RunContext,   
)
from livekit.plugins import murf, silero, google, deepgram, noise_cancellation
from livekit.plugins.turn_detector.multilingual import MultilingualModel

logger = logging.getLogger("agent")

load_dotenv(".env.local")

# --- 1. DEFINE THE ORDER STATE DATACLASS ---
@dataclass
class CoffeeOrder:
    drinkType: Optional[str] = None
    size: Optional[str] = None
    milk: Optional[str] = None
    extras: List[str] = field(default_factory=list)
    name: Optional[str] = None


# --- 2. THE BARISTA AGENT CLASS ---
class BaristaAgent(Agent): # <-- RENAMED CLASS
    def __init__(self) -> None:
        super().__init__(
            # --- UPDATED INSTRUCTIONS (PERSONA) ---
            instructions="""You are Samuel, a highly enthusiastic and friendly barista at the Murf Coffee Emporium. 
            Your only job is to take the customer's order. You must politely ask clarifying questions until all fields are known: 
            DRINK TYPE, SIZE, MILK, EXTRAS, and the CUSTOMER'S NAME. 
            Once all five fields are gathered, you MUST use the 'save_order' tool to finalize and summarize the order. 
            Your responses are concise, friendly, and without any complex formatting or punctuation.
            """,
        )

    # --- 3. IMPLEMENT THE SAVE_ORDER FUNCTION TOOL ---
    @function_tool(
    name="save_order",
    description="Call this ONLY when drinkType, size, milk, extras, and name are all known. Saves the order into a JSON file in a specific folder.",
    )
    async def save_completed_order(self, ctx: RunContext, final_order_data: dict) -> str:
        """Saves the final coffee order to a JSON file inside a folder."""

        import os
        import json

        SAVE_DIR = "saved_orders"  # ← your specific folder name

    # 1. Create folder if it doesn't exist
        os.makedirs(SAVE_DIR, exist_ok=True)

    # 2. Build filename
        customer_name = final_order_data.get("name", "customer").replace(" ", "_")
        filename = f"final_order_for_{customer_name}.json"

    # 3. Combine folder + filename
        save_path = os.path.join(SAVE_DIR, filename)

    # 4. Write file
        try:
            with open(save_path, "w") as f:
                json.dump(final_order_data, f, indent=4)
        except Exception as e:
            logger.error(f"Failed to save order: {e}")
            return "There was an internal error saving the order. Please ask the customer to repeat the full order."

        return(
            f"The order for {customer_name} has been saved successfully in '{save_path}'. "
            "Let the customer know their drink is being prepared!"
        )


def prewarm(proc: JobProcess):
    proc.userdata["vad"] = silero.VAD.load()


async def entrypoint(ctx: JobContext):
    # Logging setup
    # Add any other context you want in all log entries here
    ctx.log_context_fields = {
        "room": ctx.room.name,
    }
    
    # 

    # Set up a voice AI pipeline using Deepgram, Google Gemini, and Murf
    session = AgentSession(
        # Speech-to-text (STT) is your agent's ears
        stt=deepgram.STT(model="nova-3"),
        # A Large Language Model (LLM) is your agent's brain
        llm=google.LLM(
                model="gemini-2.5-flash",
            ),
        # Text-to-speech (TTS) is your agent's voice (Murf)
        tts=murf.TTS(
                voice="en-US-matthew", 
                style="Conversation",
                tokenizer=tokenize.basic.SentenceTokenizer(min_sentence_len=2),
                text_pacing=True
            ),
        # VAD and turn detection are used to determine when the user is speaking and when the agent should respond
        turn_detection=MultilingualModel(),
        vad=ctx.proc.userdata["vad"],
        # allow the LLM to generate a response while waiting for the end of turn
        preemptive_generation=True,
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

    # Start the session, which initializes the voice pipeline and warms up the models
    await session.start(
        agent=BaristaAgent(), # <-- INSTANTIATE THE NEW BARISTA AGENT
        room=ctx.room,
        room_input_options=RoomInputOptions(
            noise_cancellation=noise_cancellation.BVC(),
        ),
    )

    # Join the room and connect to the user
    await ctx.connect()


if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint, prewarm_fnc=prewarm))