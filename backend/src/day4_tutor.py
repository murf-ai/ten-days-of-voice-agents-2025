from __future__ import annotations

import json
import logging
import os
import re
from datetime import datetime
import asyncio
from typing import Dict, List, Optional

from dotenv import load_dotenv

# LiveKit imports
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

logger = logging.getLogger("day4_tutor")

load_dotenv(".env.local")

# -------------------------------------------------------------------
# Path configuration
# -------------------------------------------------------------------

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
CONTENT_PATH = os.path.join(BASE_DIR, "..", "shared-data", "day4_tutor_content.json")

# -------------------------------------------------------------------
# Content loading
# -------------------------------------------------------------------

def load_content(path: str = CONTENT_PATH) -> List[Dict]:
    """Load the course content JSON file."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        logger.error("Failed to load course content.")
        return []


CONTENT = load_content()

# Mode → Murf voice map
VOICE_MAP = {
    "learn": "en-US-matthew",
    "quiz": "en-US-alicia",
    "teach_back": "en-US-ken",
}

# -------------------------------------------------------------------
# Tools for LLM Agent
# -------------------------------------------------------------------

@function_tool
async def get_concept(ctx: RunContext, concept_id: Optional[str] = None) -> Dict:
    """Return a concept by ID or title. Defaults to the first."""
    if not CONTENT:
        return {}

    if not concept_id:
        return CONTENT[0]

    query = concept_id.strip().lower()

    for c in CONTENT:
        if c.get("id") == query or c.get("title", "").lower() == query:
            return c

    return CONTENT[0]


@function_tool
async def switch_mode(ctx: RunContext, mode: str) -> str:
    """Request the session to switch teaching mode (and voice)."""
    m = mode.strip().lower()

    if m not in VOICE_MAP:
        return f"unknown_mode:{m}"

    logger.info(f"Mode switch requested: {m}")

    # Persist request so the running session can pick it up and update its TTS
    try:
        tmp_dir = os.path.join(BASE_DIR, "..", "tmp")
        os.makedirs(tmp_dir, exist_ok=True)
        path = os.path.join(tmp_dir, "day4_mode_request.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"mode": m, "ts": datetime.utcnow().isoformat()}, f)
    except Exception:
        logger.exception("failed to write mode request file")

    return f"switched:{m}"


# -------------------------------------------------------------------
# Active Recall Agent
# -------------------------------------------------------------------

class TeachTheTutorAgent(Agent):
    """Voice-based Active Recall tutor (Learn / Quiz / Teach-back modes)."""

    def __init__(self, initial_mode: str = "learn") -> None:
        summaries = [f"- {c.get('id')}: {c.get('title')}" for c in CONTENT]
        content_list = "\n".join(summaries)

        instructions = (
            "You are an Active Recall Coach called 'Teach-the-Tutor'.\n"
            "Your job:\n"
            "- Greet the user.\n"
            "- Ask which mode they prefer (learn, quiz, teach_back).\n"
            "- Teach concepts using the provided content.\n"
            "Available concepts:\n"
            f"{content_list}\n\n"
            "Mode behavior:\n"
            "- learn: explain the concept using the summary.\n"
            "- quiz: ask the sample question, accept short answers, and reflect.\n"
            "- teach_back: ask the user to explain the concept and give qualitative feedback.\n\n"
            "You may use:\n"
            "- get_concept(concept_id)\n"
            "- switch_mode(mode)\n\n"
            "Keep responses short. Avoid medical or diagnostic advice.\n"
            "End interactions with: 'Does this sound right?'"
        )

        super().__init__(instructions=instructions, tools=[get_concept, switch_mode])


# -------------------------------------------------------------------
# LiveKit Voice Agent Entry Point
# -------------------------------------------------------------------

def prewarm(proc: JobProcess):
    proc.userdata["vad"] = silero.VAD.load()


async def entrypoint(ctx: JobContext):
    ctx.log_context_fields = {"room": ctx.room.name}

    default_voice = VOICE_MAP["learn"]

    session = AgentSession(
        stt=deepgram.STT(model="nova-3"),
        llm=google.LLM(model="gemini-2.5-flash"),
        tts=murf.TTS(
            voice=default_voice,
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
    def _on_metrics(ev: MetricsCollectedEvent):
        metrics.log_metrics(ev.metrics)
        usage_collector.collect(ev.metrics)

    async def log_usage():
        logger.info(f"Usage Summary: {usage_collector.get_summary()}")

    ctx.add_shutdown_callback(log_usage)

    await session.start(
        agent=TeachTheTutorAgent(initial_mode="learn"),
        room=ctx.room,
        room_input_options=RoomInputOptions(noise_cancellation=noise_cancellation.BVC()),
    )

    # Start a background watcher that applies requested mode changes by updating session TTS
    async def _watch_mode_requests():
        tmp_dir = os.path.join(BASE_DIR, "..", "tmp")
        path = os.path.join(tmp_dir, "day4_mode_request.json")
        last_ts = None
        while True:
            try:
                if os.path.exists(path):
                    with open(path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    mode = data.get("mode")
                    ts = data.get("ts")
                    if ts != last_ts and mode in VOICE_MAP:
                        last_ts = ts
                        new_voice = VOICE_MAP[mode]
                        try:
                            session._tts = murf.TTS(
                                voice=new_voice,
                                style="Conversation",
                                tokenizer=tokenize.basic.SentenceTokenizer(min_sentence_len=2),
                                text_pacing=True,
                            )
                            logger.info(f"Updated session TTS to voice '{new_voice}' for mode '{mode}'")
                        except Exception:
                            logger.exception("Failed to update session TTS")
                await asyncio.sleep(0.5)
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("Mode watcher error")
                await asyncio.sleep(1.0)

    watcher = asyncio.create_task(_watch_mode_requests())

    async def _stop_watcher():
        watcher.cancel()
        try:
            await watcher
        except Exception:
            pass

    ctx.add_shutdown_callback(_stop_watcher)

    await ctx.connect()


# -------------------------------------------------------------------
# CLI MODE IMPLEMENTATION
# -------------------------------------------------------------------

MODE_LEARN = "learn"
MODE_QUIZ = "quiz"
MODE_TEACH = "teach_back"
VALID_MODES = [MODE_LEARN, MODE_QUIZ, MODE_TEACH]


def find_concept(content: List[Dict], query: Optional[str]) -> Dict:
    if not query:
        return content[0]

    q = query.strip().lower()

    # Direct match
    for c in content:
        if c.get("id") == q or c.get("title", "").lower() == q:
            return c

    # Substring match
    for c in content:
        if q in c.get("title", "").lower():
            return c

    return content[0]


def sanitize_text(s: str) -> List[str]:
    return re.findall(r"\w+", s.lower())


def score_teach_back(reference: str, user_answer: str) -> Dict:
    """Simple keyword-based feedback scoring."""
    ref_words = set(sanitize_text(reference))
    ans_words = set(sanitize_text(user_answer))
    overlap = ref_words & ans_words

    ratio = len(overlap) / len(ref_words) if ref_words else 0

    if ratio > 0.66 and len(overlap) >= 3:
        grade = "excellent"
        message = "Great explanation! You covered the core ideas clearly."
    elif ratio > 0.33:
        grade = "good"
        message = "Good attempt — you captured several key points."
    else:
        grade = "needs_improvement"
        message = "Try focusing on the main idea and add a simple example."

    return {
        "ratio": round(ratio, 2),
        "common_words": sorted(list(overlap))[:10],
        "grade": grade,
        "message": message,
    }


# Mode runner functions --------------------------------------------------

def run_learn(concept: Dict):
    print(f"\n--- Learn: {concept.get('title')} ---\n")
    print(concept.get("summary", "(no summary available)"))


def run_quiz(concept: Dict):
    print(f"\n--- Quiz: {concept.get('title')} ---\n")
    print("Question:", concept.get("sample_question", "Explain this concept."))


def run_teach_back(concept: Dict):
    print(f"\n--- Teach Back: {concept.get('title')} ---\n")
    print("Please explain this concept back:")
    print(concept.get("sample_question", "Explain in your own words."))


# CLI REPL --------------------------------------------------------------

def cli_main():
    content = load_content()
    current_concept = content[0]
    current_mode = None

    print("Welcome to Teach-the-Tutor (CLI Mode).")
    print("Modes: learn, quiz, teach_back")
    print("Type a mode to begin or type 'help'.")

    while True:
        # Mode selection
        if not current_mode:
            inp = input("Mode> ").strip().lower()
            if inp in ("quit", "exit"):
                print("Goodbye!")
                break

            if inp in VALID_MODES:
                current_mode = inp
                if inp == MODE_LEARN:
                    run_learn(current_concept)
                elif inp == MODE_QUIZ:
                    run_quiz(current_concept)
                else:
                    run_teach_back(current_concept)
                continue

            if inp.startswith("help"):
                print("Commands: learn, quiz, teach_back, list concepts, change concept <id|title>, quit")
                continue

            if inp.startswith("list"):
                for c in content:
                    print(f"- {c['id']}: {c['title']}")
                continue

            if inp.startswith("change concept"):
                arg = inp.replace("change concept", "").strip()
                current_concept = find_concept(content, arg)
                print(f"Concept changed to: {current_concept.get('title')}")
                continue

            print("Unknown command.")
            continue

        # Inside a mode
        user_input = input("You> ").strip()

        if user_input.lower() in ("quit", "exit"):
            print("Goodbye!")
            break

        if user_input.lower().startswith("switch to"):
            mode = user_input.lower().replace("switch to", "").strip()
            if mode in VALID_MODES:
                current_mode = mode
                if mode == MODE_LEARN:
                    run_learn(current_concept)
                elif mode == MODE_QUIZ:
                    run_quiz(current_concept)
                else:
                    run_teach_back(current_concept)
            else:
                print("Invalid mode.")
            continue

        if user_input.lower().startswith("change concept"):
            arg = user_input.split(maxsplit=2)[-1]
            current_concept = find_concept(content, arg)
            print(f"Concept changed to: {current_concept.get('title')}")
            continue

        # Mode logic
        if current_mode == MODE_LEARN:
            print("If you want a quiz next, type: switch to quiz")

        elif current_mode == MODE_QUIZ:
            score = score_teach_back(current_concept.get("summary", ""), user_input)
            print("Feedback:", score["message"])

        elif current_mode == MODE_TEACH:
            score = score_teach_back(current_concept.get("summary", ""), user_input)
            print("Coach feedback:", score["message"])
            print("Matched:", ", ".join(score["common_words"]))
            print(f"Score: {score['ratio'] * 100:.0f}%")


# -------------------------------------------------------------------
# Main Entry (Runs CLI or Worker)
# -------------------------------------------------------------------

if __name__ == "__main__":
    # If running with `python day4_tutor.py`, launch CLI
    if os.environ.get("TUTOR_MODE") == "cli":
        cli_main()
    else:
        # Otherwise run LiveKit Worker
        cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint, prewarm_fnc=prewarm))
