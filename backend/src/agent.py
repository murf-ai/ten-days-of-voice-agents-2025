import logging
import asyncio 
import json
import os
import random
from typing import Literal, Optional
from dataclasses import dataclass, field

from dotenv import load_dotenv
from livekit.agents import (
    Agent,
    AgentSession,
    JobContext,
    JobProcess,
    MetricsCollectedEvent,
    WorkerOptions,
    cli,
    metrics,
    tokenize,
    function_tool,
    RunContext
)
from livekit.plugins import murf, silero, google, deepgram
from livekit.plugins.turn_detector.multilingual import MultilingualModel

logger = logging.getLogger("agent")
load_dotenv(".env.local")

# --- Load Tutor Content ---
CONTENT_FILE = "shared-data/day4_tutor_content.json"


def load_tutor_content():
    """Load learning content from JSON file."""
    try:
        with open(CONTENT_FILE, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        logger.error(f"Content file not found: {CONTENT_FILE}")
        return []


TUTOR_CONTENT = load_tutor_content()
CONCEPT_IDS = [concept["id"] for concept in TUTOR_CONTENT]

# --- Session State ---


@dataclass
class TutorState:
    """Tracks the current learning session state."""
    current_mode: str = "welcome"  # welcome, learn, quiz, teach_back
    current_concept_id: Optional[str] = None

    def get_concept(self):
        """Get the current concept data."""
        if not self.current_concept_id:
            return None
        return next((c for c in TUTOR_CONTENT if c["id"] == self.current_concept_id), None)

# --- Tools for Mode Switching ---


@function_tool
async def switch_mode(
    context: RunContext,
    mode: Literal["learn", "quiz", "teach_back"],
    concept_id: Optional[str] = None
) -> str:
    """
    Switch to a different learning mode.

    Args:
        mode: The learning mode to switch to (learn, quiz, or teach_back)
        concept_id: Optional concept ID to focus on. If not provided, keeps current or picks random.
    """
    state: TutorState = context.userdata["tutor_state"]

    # Update concept if provided
    if concept_id and concept_id in CONCEPT_IDS:
        state.current_concept_id = concept_id
    elif not state.current_concept_id:
        state.current_concept_id = random.choice(CONCEPT_IDS)

    # Update mode
    state.current_mode = mode

    concept = state.get_concept()
    if not concept:
        return "Error: Could not load concept. Please try again."

    return f"MODE_SWITCH:{mode}:{concept['id']}"

# --- Orchestrator Agent (Main Greeter) ---


class OrchestratorAgent(Agent):
    """Main agent that greets and routes to learning modes."""

    def __init__(self, llm) -> None:
        super().__init__(
            instructions=(
                "You are the Teach-the-Tutor Coach, a friendly learning assistant. "
                "\n\n"
                "GREETING: Start by saying: 'Welcome to Teach-the-Tutor! I'm your Active Recall Coach. "
                "I can help you learn programming concepts through three modes: "
                "Learn (I explain), Quiz (I test you), and Teach Back (you explain to me). "
                "Which mode would you like to start with?'"
                "\n\n"
                f"AVAILABLE CONCEPTS: {', '.join([c['title'] for c in TUTOR_CONTENT])}"
                "\n\n"
                "When user chooses a mode, call the switch_mode tool immediately with their choice. "
                "You can also switch concepts by using the concept_id parameter."
            ),
            tools=[switch_mode],
            llm=llm
        )

# --- Learn Mode Agent ---


class LearnAgent(Agent):
    """Agent that explains concepts (Matthew voice)."""

    def __init__(self, llm, concept) -> None:
        super().__init__(
            instructions=(
                f"You are in LEARN mode using Matthew's voice. "
                f"The current concept is **{concept['title']}**. "
                f"\n\n"
                f"Explain this concept clearly: {concept['summary']}"
                f"\n\n"
                "After explaining, ask: 'Would you like to try a quiz on this, "
                "or would you prefer to teach it back to me? Or pick a different concept?'"
                "\n\n"
                "When user wants to switch, call switch_mode tool with their choice."
            ),
            tools=[switch_mode],
            llm=llm
        )

# --- Quiz Mode Agent ---


class QuizAgent(Agent):
    """Agent that quizzes the user (Alicia voice)."""

    def __init__(self, llm, concept) -> None:
        super().__init__(
            instructions=(
                f"You are in QUIZ mode using Alicia's voice. "
                f"The current concept is **{concept['title']}**. "
                f"\n\n"
                f"Ask this question: {concept['sample_question']}"
                f"\n\n"
                "Wait for the user's answer, then provide feedback on their response. "
                "After feedback, ask: 'Would you like to learn more about this concept, "
                "or try teaching it back to me? Or switch to a different concept?'"
                "\n\n"
                "When user wants to switch, call switch_mode tool with their choice."
            ),
            tools=[switch_mode],
            llm=llm
        )

# --- Teach Back Mode Agent ---


class TeachBackAgent(Agent):
    """Agent that has user explain back (Ken voice)."""

    def __init__(self, llm, concept) -> None:
        super().__init__(
            instructions=(
                f"You are in TEACH BACK mode using Ken's voice. "
                f"The current concept is **{concept['title']}**. "
                f"\n\n"
                f"Ask the user: 'Please explain {concept['title']} to me in your own words.'"
                f"\n\n"
                "Listen carefully to their explanation. Then provide qualitative feedback: "
                "- What they got right "
                "- What they might have missed "
                "- Overall assessment (good, needs work, excellent, etc.)"
                "\n\n"
                "After feedback, ask: 'Would you like to learn more about this concept, "
                "or try a quiz? Or switch to a different concept?'"
                "\n\n"
                "When user wants to switch, call switch_mode tool with their choice."
            ),
            tools=[switch_mode],
            llm=llm
        )

# --- Voice Configuration Helper ---


def get_tts_for_mode(mode: str):
    """Get the appropriate TTS voice for each mode."""
    voice_mapping = {
        "welcome": "en-US-matthew",
        "learn": "en-US-matthew",
        "quiz": "en-US-alicia",
        "teach_back": "en-US-ken"
    }
    voice = voice_mapping.get(mode, "en-US-matthew")

    return murf.TTS(
        voice=voice,
        style="Conversation",
        tokenizer=tokenize.basic.SentenceTokenizer(min_sentence_len=2),
        text_pacing=True
    )

# --- Main Session Logic ---


async def entrypoint(ctx: JobContext):
    """Main entrypoint that handles mode switching."""

    # Initialize state
    tutor_state = TutorState()

    ctx.log_context_fields = {"room": ctx.room.name}
    llm = google.LLM(model="gemini-2.5-flash")

    # Start with orchestrator
    current_agent = OrchestratorAgent(llm=llm)
    current_tts = get_tts_for_mode("welcome")

    session = AgentSession(
        stt=deepgram.STT(model="nova-3"),
        llm=llm,
        tts=current_tts,
        turn_detection=MultilingualModel(),
        vad=silero.VAD.load(),
        preemptive_generation=True,
    )

    session.userdata = {"tutor_state": tutor_state}

    # Metrics
    usage_collector = metrics.UsageCollector()

    @session.on("metrics_collected")
    def _on_metrics_collected(ev: MetricsCollectedEvent):
        metrics.log_metrics(ev.metrics)
        usage_collector.collect(ev.metrics)

    async def log_usage():
        summary = usage_collector.get_summary()
        logger.info(f"Usage: {summary}")

    ctx.add_shutdown_callback(log_usage)

    # Start session
    await session.start(agent=current_agent, room=ctx.room)
    await ctx.connect()

    # Monitor for mode switches
    while True:
        await asyncio.sleep(0.5)

        if tutor_state.current_mode in ["learn", "quiz", "teach_back"]:
            concept = tutor_state.get_concept()
            if concept:
                # Switch agent and voice
                if tutor_state.current_mode == "learn":
                    new_agent = LearnAgent(llm=llm, concept=concept)
                    new_tts = get_tts_for_mode("learn")
                elif tutor_state.current_mode == "quiz":
                    new_agent = QuizAgent(llm=llm, concept=concept)
                    new_tts = get_tts_for_mode("quiz")
                else:  # teach_back
                    new_agent = TeachBackAgent(llm=llm, concept=concept)
                    new_tts = get_tts_for_mode("teach_back")

                # Update session
                session.agent = new_agent
                session.tts = new_tts

                logger.info(
                    f"Switched to {tutor_state.current_mode} mode for {concept['title']}")


def prewarm(proc: JobProcess):
    """Preload VAD model."""
    pass


if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint, prewarm_fnc=prewarm))
