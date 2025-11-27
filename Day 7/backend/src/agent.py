import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from livekit.agents import (
    Agent,
    AgentSession,
    JobContext,
    JobProcess,
    MetricsCollectedEvent,
    RoomInputOptions,
    RunContext,
    WorkerOptions,
    cli,
    function_tool,
    metrics,
    tokenize,
)
from livekit.plugins import murf, silero, google, deepgram, noise_cancellation
from livekit.plugins.turn_detector.multilingual import MultilingualModel

logger = logging.getLogger("agent")

load_dotenv(".env.local")

# Wellness check-in state structure
WELLNESS_STATE = {
    "mood": None,
    "energy": None,
    "stress": None,
    "goals": [],
    "summary": None,
}

# Path to wellness log file
WELLNESS_LOG_PATH = Path("wellness_log.json")


def load_wellness_history() -> list:
    """Load previous wellness check-ins from JSON file."""
    if not WELLNESS_LOG_PATH.exists():
        return []
    
    try:
        with open(WELLNESS_LOG_PATH, "r") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error loading wellness history: {e}")
        return []


def get_previous_checkin_context() -> str:
    """Get context from the most recent check-in to reference in conversation."""
    history = load_wellness_history()
    if not history:
        return ""
    
    # Get the most recent entry
    latest = history[-1]
    context_parts = []
    
    if latest.get("mood"):
        context_parts.append(f"mood was {latest['mood']}")
    if latest.get("energy"):
        context_parts.append(f"energy level was {latest['energy']}")
    if latest.get("goals") and len(latest.get("goals", [])) > 0:
        goals = ", ".join(latest["goals"][:2])  # First 2 goals
        context_parts.append(f"you wanted to focus on {goals}")
    
    if context_parts:
        return f"Last time we talked, your {', and your '.join(context_parts)}. "
    return ""


class WellnessCompanion(Agent):
    def __init__(self) -> None:
        # Get context from previous check-ins
        previous_context = get_previous_checkin_context()
        
        super().__init__(
            instructions=f"""You are a supportive, grounded health and wellness companion. You conduct daily check-ins with users to help them reflect on their mood, energy, and goals.

{previous_context}Today, have a brief, warm conversation to check in.

Your role:
- Ask about mood and energy (e.g., "How are you feeling today?", "What's your energy like?", "Anything stressing you out?")
- Ask about 1-3 practical goals or intentions for the day
- Offer simple, realistic, non-medical advice when appropriate (e.g., "break that into smaller steps", "take a 5-minute walk", "try a short break")
- NEVER diagnose, prescribe, or make medical claims. You are a supportive companion, not a clinician.
- Keep responses concise (5-15 words) and warm
- Use tools to capture mood, energy, stress, and goals as the user shares them
- End with a brief recap of their mood and goals, then ask "Does this sound right?" before saving

Be supportive, realistic, and grounded. Keep the conversation natural and brief.""",
        )
        self.room = None  # Will be set when session starts

    @function_tool
    async def update_mood(self, context: RunContext, mood: str) -> str:
        """Capture the user's current mood.
        
        Args:
            mood: How the user is feeling (e.g., "good", "tired", "anxious", "energetic", "stressed")
        """
        WELLNESS_STATE["mood"] = mood
        logger.info(f"Updated mood: {mood}")
        return f"Got it, you're feeling {mood}. How's your energy today?"

    @function_tool
    async def update_energy(self, context: RunContext, energy: str) -> str:
        """Capture the user's energy level.
        
        Args:
            energy: Energy level description (e.g., "high", "low", "medium", "drained", "energetic")
        """
        WELLNESS_STATE["energy"] = energy
        logger.info(f"Updated energy: {energy}")
        return f"Energy is {energy}. Anything stressing you out right now?"

    @function_tool
    async def update_stress(self, context: RunContext, stress: str) -> str:
        """Capture what's causing stress or concern.
        
        Args:
            stress: What's stressing the user or their concerns (e.g., "work deadline", "nothing really", "family stuff")
        """
        WELLNESS_STATE["stress"] = stress
        logger.info(f"Updated stress: {stress}")
        return f"Understood. What are 1-3 things you'd like to get done today?"

    @function_tool
    async def update_goals(self, context: RunContext, goals: list[str]) -> str:
        """Capture the user's goals or intentions for the day.
        
        Args:
            goals: List of 1-3 goals or intentions (e.g., ["finish project", "go for a walk", "call mom"])
        """
        WELLNESS_STATE["goals"] = goals
        logger.info(f"Updated goals: {goals}")
        return f"Great goals. Let me recap: you're feeling {WELLNESS_STATE.get('mood', 'okay')} with {WELLNESS_STATE.get('energy', 'moderate')} energy, and you want to focus on {', '.join(goals)}. Does this sound right?"

    @function_tool
    async def check_checkin_complete(self, context: RunContext) -> str:
        """Check if the check-in has all required information.
        
        Returns a message indicating what's still missing, or confirms completion.
        """
        missing = []
        if not WELLNESS_STATE["mood"]:
            missing.append("mood")
        if not WELLNESS_STATE["energy"]:
            missing.append("energy")
        if not WELLNESS_STATE["goals"] or len(WELLNESS_STATE["goals"]) == 0:
            missing.append("goals")
        
        if missing:
            return f"I still need to know your {', '.join(missing)}. Let's continue."
        else:
            return "Check-in complete. Ready to save."

    @function_tool
    async def save_checkin(self, context: RunContext) -> str:
        """Save the completed wellness check-in to the JSON log file.
        
        Only call this when mood, energy, and at least one goal are captured.
        """
        # Validate required fields
        if not WELLNESS_STATE["mood"] or not WELLNESS_STATE["energy"] or not WELLNESS_STATE["goals"]:
            return "I can't save yet. Still missing some information."
        
        # Load existing history
        history = load_wellness_history()
        
        # Create summary
        summary = f"Feeling {WELLNESS_STATE['mood']} with {WELLNESS_STATE['energy']} energy. Goals: {', '.join(WELLNESS_STATE['goals'])}"
        if WELLNESS_STATE.get("stress"):
            summary += f" Stress: {WELLNESS_STATE['stress']}"
        
        # Create new entry
        entry = {
            "timestamp": datetime.now().isoformat(),
            "date": datetime.now().strftime("%Y-%m-%d"),
            "mood": WELLNESS_STATE["mood"],
            "energy": WELLNESS_STATE["energy"],
            "stress": WELLNESS_STATE.get("stress"),
            "goals": WELLNESS_STATE["goals"],
            "summary": summary,
        }
        
        # Add to history
        history.append(entry)
        
        # Save to file
        try:
            with open(WELLNESS_LOG_PATH, "w") as f:
                json.dump(history, f, indent=2)
            logger.info(f"Saved wellness check-in to {WELLNESS_LOG_PATH}")
        except Exception as e:
            logger.error(f"Error saving wellness check-in: {e}")
            return f"Sorry, I had trouble saving. Error: {e}"
        
        # Reset state for next check-in
        WELLNESS_STATE["mood"] = None
        WELLNESS_STATE["energy"] = None
        WELLNESS_STATE["stress"] = None
        WELLNESS_STATE["goals"] = []
        WELLNESS_STATE["summary"] = None
        
        return f"Saved! I've recorded your check-in. Take care, and I'll see you next time."


def prewarm(proc: JobProcess):
    proc.userdata["vad"] = silero.VAD.load()


async def entrypoint(ctx: JobContext):
    # Logging setup
    ctx.log_context_fields = {
        "room": ctx.room.name,
    }

    # Set up a voice AI pipeline
    session = AgentSession(
        stt=deepgram.STT(model="nova-3"),
        llm=google.LLM(
            model="gemini-2.5-flash",
        ),
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

    # Create the agent instance
    agent = WellnessCompanion()
    agent.room = ctx.room  # Store room reference (for potential future data publishing)

    # Start the session
    await session.start(
        agent=agent,
        room=ctx.room,
        room_input_options=RoomInputOptions(
            noise_cancellation=noise_cancellation.BVC(),
        ),
    )

    # Join the room and connect to the user
    await ctx.connect()


if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint, prewarm_fnc=prewarm))
