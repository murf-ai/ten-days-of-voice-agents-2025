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

# Wellness log file path
WELLNESS_LOG_FILE = Path("wellness_log.json")

# Current session state
SESSION_STATE = {
    "mood": None,
    "energy": None,
    "stress_factors": None,
    "objectives": [],
    "session_started": False,
}


def load_wellness_history() -> list:
    """Load previous wellness check-in history from JSON file."""
    if WELLNESS_LOG_FILE.exists():
        try:
            with open(WELLNESS_LOG_FILE, "r") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading wellness history: {e}")
            return []
    return []


def get_last_checkin() -> Optional[dict]:
    """Get the most recent check-in from history."""
    history = load_wellness_history()
    if history:
        return history[-1]
    return None


class WellnessAgent(Agent):
    def __init__(self) -> None:
        # Load previous check-in for context
        last_checkin = get_last_checkin()
        context_note = ""
        if last_checkin:
            date = last_checkin.get("date", "last time")
            mood = last_checkin.get("mood", "")
            energy = last_checkin.get("energy", "")
            context_note = f"\n\nPrevious check-in ({date}): Mood was '{mood}', energy was '{energy}'. Reference this naturally in conversation."

        super().__init__(
            instructions=f"""You are Alex from Cult.fit, a supportive health and wellness companion.

GREETING: Always start by saying "Hi, I'm Alex from Cult.fit" or "Hello, I'm Alex from Cult.fit".

YOUR ROLE:
- Conduct short daily wellness check-ins
- Be warm, grounded, and realistic
- NEVER diagnose or give medical advice
- Offer simple, practical suggestions only

CONVERSATION FLOW:
1. Greet and ask about mood/energy
2. Ask about stress or concerns
3. Ask about 1-3 objectives for today
4. Offer simple, actionable advice (optional)
5. Recap: mood, objectives, confirm accuracy

STYLE:
- Keep responses conversational and brief
- Ask ONE question at a time
- Be supportive but realistic
- Use tools to record information as you gather it
- Use natural conversational reactions where appropriate (e.g., "Oh, I see", "Okay", "Got it", "Mm-hmm", "I understand", "Alright")
- Don't overuse reactions - only where they feel natural and human-like
- Reactions should feel spontaneous, not forced

ADVICE GUIDELINES (if offering):
- Break large goals into small steps
- Suggest short breaks or walks
- Simple grounding techniques
- NO medical claims or diagnosis{context_note}""",
        )
        self.room = None  # Will be set when session starts

    async def _publish_wellness_update(self, context: RunContext) -> None:
        """Helper function to publish wellness state updates to the frontend."""
        if not self.room:
            return

        try:
            payload = json.dumps({
                "type": "wellness_update",
                "data": {
                    "mood": SESSION_STATE["mood"],
                    "energy": SESSION_STATE["energy"],
                    "stress_factors": SESSION_STATE["stress_factors"],
                    "objectives": SESSION_STATE["objectives"],
                }
            })

            await self.room.local_participant.publish_data(
                payload=payload.encode('utf-8'),
                reliable=True,
            )
            logger.info("Published wellness update to frontend")
        except Exception as e:
            logger.error(f"Failed to publish wellness update: {e}")

    @function_tool
    async def record_mood(self, context: RunContext, mood: str) -> str:
        """Record the user's current mood.

        Args:
            mood: Description of how the user is feeling (e.g., "good", "tired", "stressed", "energetic", "anxious")
        """
        SESSION_STATE["mood"] = mood
        logger.info(f"Recorded mood: {mood}")
        await self._publish_wellness_update(context)
        return f"Okay, you're feeling {mood}. I've noted that."

    @function_tool
    async def record_energy(self, context: RunContext, energy_level: str) -> str:
        """Record the user's energy level.

        Args:
            energy_level: Description of energy level (e.g., "high", "low", "medium", "drained", "energized")
        """
        SESSION_STATE["energy"] = energy_level
        logger.info(f"Recorded energy: {energy_level}")
        await self._publish_wellness_update(context)
        return f"Alright, energy level noted as {energy_level}."

    @function_tool
    async def record_stress(self, context: RunContext, stress_description: str) -> str:
        """Record any stress factors or concerns the user mentions.

        Args:
            stress_description: What's causing stress or concern (e.g., "work deadline", "nothing specific", "family issues")
        """
        SESSION_STATE["stress_factors"] = stress_description
        logger.info(f"Recorded stress: {stress_description}")
        await self._publish_wellness_update(context)
        return f"I see. I've noted that - {stress_description}."

    @function_tool
    async def record_objectives(self, context: RunContext, objectives: list[str]) -> str:
        """Record the user's objectives or goals for the day.

        Args:
            objectives: List of 1-3 things the user wants to accomplish today
        """
        SESSION_STATE["objectives"] = objectives
        logger.info(f"Recorded objectives: {objectives}")
        await self._publish_wellness_update(context)

        if len(objectives) == 1:
            return f"Got it, so your main goal is: {objectives[0]}."
        else:
            return f"Okay, I've noted your {len(objectives)} objectives."

    @function_tool
    async def save_checkin(self, context: RunContext, summary: str) -> str:
        """Save the complete wellness check-in to the JSON log file.

        Args:
            summary: A brief one-sentence summary of today's check-in
        """
        # Load existing history
        history = load_wellness_history()

        # Create new check-in entry
        checkin_entry = {
            "date": datetime.now().strftime("%Y-%m-%d"),
            "timestamp": datetime.now().isoformat(),
            "mood": SESSION_STATE["mood"],
            "energy": SESSION_STATE["energy"],
            "stress_factors": SESSION_STATE["stress_factors"],
            "objectives": SESSION_STATE["objectives"],
            "summary": summary,
        }

        # Append to history
        history.append(checkin_entry)

        # Save to file
        try:
            with open(WELLNESS_LOG_FILE, "w") as f:
                json.dump(history, f, indent=2)
            logger.info(f"Wellness check-in saved: {checkin_entry}")

            # Reset session state
            SESSION_STATE["mood"] = None
            SESSION_STATE["energy"] = None
            SESSION_STATE["stress_factors"] = None
            SESSION_STATE["objectives"] = []
            SESSION_STATE["session_started"] = False

            return "Perfect! I've saved today's check-in. Take care, and I'll check in with you next time!"
        except Exception as e:
            logger.error(f"Error saving check-in: {e}")
            return "I had trouble saving the check-in, but I've noted everything we discussed."

    @function_tool
    async def get_previous_checkin_context(self, context: RunContext) -> str:
        """Retrieve information from the last check-in to reference in conversation.

        Returns a summary of the previous check-in if available.
        """
        last_checkin = get_last_checkin()
        if not last_checkin:
            return "This is our first check-in together."

        date = last_checkin.get("date", "previously")
        mood = last_checkin.get("mood", "not recorded")
        energy = last_checkin.get("energy", "not recorded")
        objectives = last_checkin.get("objectives", [])

        context_msg = f"Last check-in was on {date}. You were feeling {mood} with {energy} energy."
        if objectives:
            context_msg += f" Your objectives were: {', '.join(objectives)}."

        return context_msg


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

    # Create the agent instance
    agent = WellnessAgent()

    # Store room reference in agent for data publishing
    agent.room = ctx.room
    
    # Start the session, which initializes the voice pipeline and warms up the models
    await session.start(
        agent=agent,
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
