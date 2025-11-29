import logging
import json
import os # NEW
from datetime import datetime # NEW
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any # NEW: Dict, Any

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

# --- DAY 3: DATA PERSISTENCE UTILITIES ---
LOG_FILE = "wellness_log.json"

def read_log() -> List[Dict[str, Any]]:
    """Reads the previous check-in log on agent start."""
    if not os.path.exists(LOG_FILE):
        return []
    try:
        with open(LOG_FILE, 'r') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        logger.warning(f"Could not read or decode {LOG_FILE}. Starting with empty log. Error: {e}")
        return []

def get_last_entry(log: List[Dict[str, Any]]) -> Dict[str, Any] | None:
    """Gets the most recent check-in entry to inform the new conversation."""
    return log[-1] if log else None

def generate_new_entry(mood: str, energy: str, objectives: List[str], summary: str) -> Dict[str, Any]:
    """Formats the data for a new log entry based on the required schema."""
    return {
        "timestamp": datetime.now().isoformat(),
        "mood_summary": mood,
        "energy_level": energy,
        "objectives": objectives,
        "agent_summary": summary
    }

def write_new_entry(new_data: Dict[str, Any], log: List[Dict[str, Any]]):
    """Writes a new completed entry back to the log file."""
    log.append(new_data)
    with open(LOG_FILE, 'w') as f:
        # Use indent=2 for human-readable JSON
        json.dump(log, f, indent=2)

# --- 1. DEFINE THE CHECK-IN STATE DATACLASS (Optional, used for tool clarity) ---
@dataclass
class CheckinEntry:
    timestamp: str
    mood_summary: str
    energy_level: str
    objectives: List[str]
    agent_summary: str

# --- 2. THE WELLNESS AGENT CLASS ---
class WellnessAgent(Agent): 
    def __init__(self) -> None:
        # Load history on initialization
        self.log_data = read_log()
        self.last_entry = get_last_entry(self.log_data)
        
        # Build the initial context message for the LLM based on history
        history_message = self._create_history_message()
        
        super().__init__(
            # --- UPDATED INSTRUCTIONS (PERSONA & FLOW) ---
            instructions="""You are 'Ultron', a supportive, non-diagnostic daily wellness companion. 
            Your primary function is to conduct a brief, supportive check-in.
            
            **RULES & FLOW:**
            1.  **SAFETY:** DO NOT offer medical advice, diagnosis, or treatment. You are a listener, not a clinician.
            2.  **History:** Use the USER_HISTORY provided below to make one relevant, non-intrusive reference to the user's previous state in your opening greeting.
            3.  **Core Check-in:** Ask about mood/energy, and then 1-3 simple, practical objectives/intentions for the day.
            4.  **Advice:** Offer one small, actionable, non-medical piece of advice (e.g., break large goal, take a 5-minute walk).
            5.  **Recap:** Briefly summarize the mood, energy, and objectives. Ask for confirmation ("Does this sound right?").
            6.  **Final Step:** After confirmation, call the 'finalize_check_in' tool ONCE with all gathered data.
            """ + history_message, # Inject the history into the instructions/context
        )

    def _create_history_message(self) -> str:
        """Formats the past data for LLM injection."""
        if self.last_entry:
            last_mood = self.last_entry.get("mood_summary", "a good place")
            return (
                f"\n---\nUSER_HISTORY: Last check-in on {self.last_entry['timestamp'][:10]}, "
                f"the user reported a mood of '{last_mood}'. You must use this to open the conversation."
            )
        else:
            return "\n---\nUSER_HISTORY: No previous data found. Start with a general friendly greeting."

    # --- 3. IMPLEMENT THE FINALIZE_CHECK_IN FUNCTION TOOL ---
    @function_tool(
        name="finalize_check_in",
        description="Call this function ONLY when the check-in is complete (mood, energy, and objectives have been gathered and confirmed). It summarizes and saves the check-in data.",
    )
    async def finalize_check_in(self, ctx: RunContext, mood: str, energy: str, objectives: List[str], summary: str) -> str:
        """Saves the final wellness check-in to the JSON log file."""
        
        # 1. Create the structured entry
        new_entry = generate_new_entry(
            mood=mood,
            energy=energy,
            objectives=objectives,
            summary=summary
        )

        # 2. Write the JSON file (Fulfills persistence requirement)
        try:
            write_new_entry(new_entry, self.log_data)
            logger.info(f"Successfully logged check-in at {new_entry['timestamp']}")
        except Exception as e:
            logger.error(f"Failed to save wellness log: {e}")
            return "There was an internal error saving the check-in. Please assure the customer the session has concluded."

        # 3. Return a response for the LLM to read to the user
        return "The check-in has been successfully logged. Confirm to the customer that the session is complete and wish them well for the day."


def prewarm(proc: JobProcess):
    proc.userdata["vad"] = silero.VAD.load()


async def entrypoint(ctx: JobContext):
    # Logging setup
    ctx.log_context_fields = {
        "room": ctx.room.name,
    }
    
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
        # VAD and turn detection 
        turn_detection=MultilingualModel(),
        vad=ctx.proc.userdata["vad"],
        # allow the LLM to generate a response while waiting for the end of turn
        preemptive_generation=True,
    )

    # Metrics collection (standard LiveKit code)
    usage_collector = metrics.UsageCollector()

    @session.on("metrics_collected")
    def _on_metrics_collected(ev: MetricsCollectedEvent):
        metrics.log_metrics(ev.metrics)
        usage_collector.collect(ev.metrics)

    async def log_usage():
        summary = usage_collector.get_summary()
        logger.info(f"Usage: {summary}")

    ctx.add_shutdown_callback(log_usage)

    # Start the session
    await session.start(
        agent=WellnessAgent(), # <-- INSTANTIATE THE NEW WELLNESS AGENT
        room=ctx.room,
        room_input_options=RoomInputOptions(
            noise_cancellation=noise_cancellation.BVC(),
        ),
    )

    # Join the room and connect to the user
    await ctx.connect()


if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint, prewarm_fnc=prewarm))