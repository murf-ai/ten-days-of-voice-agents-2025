# backend/src/agent_day8.py
import logging
import os
import json
from datetime import datetime
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv

from livekit.agents import (
    Agent,
    AgentSession,
    JobContext,
    JobProcess,
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

logger = logging.getLogger("agent_day8")
logger.setLevel(logging.INFO)

load_dotenv(".env.local")

# ---------- Paths & optional world model ---------- #
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHARED_DIR = os.path.join(BASE_DIR, "shared-data")
os.makedirs(SHARED_DIR, exist_ok=True)
WORLD_PATH = os.path.join(SHARED_DIR, "day8_world.json")  # optional

# If you want a small structured world you can place it in day8_world.json.
# Otherwise the system prompt below will define the universe (chat-only mode).
WORLD: Dict[str, Any] = {}
if os.path.exists(WORLD_PATH):
    try:
        with open(WORLD_PATH, "r", encoding="utf-8") as f:
            WORLD = json.load(f)
    except Exception:
        WORLD = {}

# ---------- Murf TTS voices (customize if your account uses different IDs) ---------- #
TTS_GM = murf.TTS(
    voice="en-US-matthew",  # Game Master voice — change if your account uses a different id
    style="Narration",
    tokenizer=tokenize.basic.SentenceTokenizer(min_sentence_len=2),
    text_pacing=True,
)

TTS_ROUTER = TTS_GM

# ---------- Utility: simple story save/load (optional) ---------- #
STORY_LOG = os.path.join(SHARED_DIR, "day8_sessions.json")


def _append_session_log(entry: Dict[str, Any]):
    try:
        if not os.path.exists(STORY_LOG):
            with open(STORY_LOG, "w", encoding="utf-8") as f:
                json.dump([entry], f, indent=2, ensure_ascii=False)
            return
        with open(STORY_LOG, "r+", encoding="utf-8") as f:
            data = json.load(f)
            data.append(entry)
            f.seek(0)
            json.dump(data, f, indent=2, ensure_ascii=False)
            f.truncate()
    except Exception as e:
        logger.warning("Could not write session log: %s", e)


# ---------- Tools available to LLM / agent ---------- #

@function_tool
async def restart_story(ctx: RunContext) -> str:
    """Reset the in-session story state so the GM can start fresh."""
    session = ctx.session
    session.userdata["story"] = []
    session.userdata["players"] = {}
    return "Restarted the adventure. Ready for a new story."


@function_tool
async def record_player_action(ctx: RunContext, action_text: str) -> str:
    """Record an action into session.userdata['story'] (simple persistence)."""
    session = ctx.session
    story = session.userdata.setdefault("story", [])
    entry = {"ts": datetime.utcnow().isoformat(), "actor": "player", "text": action_text}
    story.append(entry)
    session.userdata["story"] = story
    return f"Recorded action: {action_text}"


# ---------- GameMaster Agent ---------- #

class GameMasterAgent(Agent):
    def __init__(self, universe: Optional[str] = None, tone: Optional[str] = "dramatic", **kwargs):
        # Compose a robust system prompt / instructions for the LLM (GM persona)
        universe_desc = universe or (
            "A pocket fantasy world of misty forests and ruined keeps (original setting)."
        )

        # If you have structured WORLD data, include a short summary for the LLM
        world_summary = ""
        if WORLD:
            world_summary = "\nWorld model:\n" + json.dumps(WORLD, indent=2)[:2000]  # truncated

        instructions = f"""
You are the Game Master (GM) for a single-player, voice-first D&D-style adventure.
Universe: {universe_desc}
Tone: {tone}

Rules (important):
- You are the GM: describe scenes, NPCs, sensory details, and end every turn with a direct prompt asking the player for an action, e.g. "What do you do?" or "How do you respond?"
- Keep descriptions concise but evocative (1-3 short paragraphs).
- Maintain continuity via chat history. Remember player choices and named entities (NPCs, places, items).
- You may call the provided tools only to record player actions or restart the story:
  - record_player_action(action_text)
  - restart_story()
- Never ask for personal data or ask the user to reveal real personal secrets.
- If the player asks to "restart", call restart_story.
- If the player asks for a hint, provide one subtle hint and then ask "What do you do?"

{world_summary}

Start by introducing the immediate scene, the player's role, and one clear immediate objective. End with a question that asks for the player's next action.
"""

        super().__init__(instructions=instructions, tts=TTS_GM, **kwargs)

    async def on_enter(self) -> None:
        # Initialize session story state if missing
        ud = self.session.userdata
        if "story" not in ud:
            ud["story"] = []
        if "players" not in ud:
            ud["players"] = {}

        # Start the adventure with a short opening scene
        await self.session.generate_reply(
            instructions=(
                "Open the adventure: introduce the player character (unnamed is OK), "
                "describe the opening location and a small immediate conflict or mystery, "
                "then ask: 'What do you do?'"
            )
        )

    async def on_exit(self) -> None:
        # When the agent session ends, optionally persist the story to a log file
        ud = getattr(self.session, "userdata", {})
        story = ud.get("story", [])
        if story:
            _append_session_log({"timestamp": datetime.utcnow().isoformat(), "story": story})


# ---------- Prewarm VAD ---------- #
def prewarm(proc: JobProcess):
    proc.userdata["vad"] = silero.VAD.load()


# ---------- Entrypoint ---------- #
async def entrypoint(ctx: JobContext):
    ctx.log_context_fields = {"room": ctx.room.name}

    session = AgentSession(
        stt=deepgram.STT(model="nova-3"),
        llm=google.LLM(model="gemini-2.5-flash"),
        tts=None,  # let agent supply tts
        turn_detection=MultilingualModel(),
        vad=ctx.proc.userdata["vad"],
        preemptive_generation=True,
        tools=[restart_story, record_player_action],
    )

    # initialize userdata: story + players
    session.userdata = {"story": [], "players": {}}

    usage_collector = metrics.UsageCollector()

    @session.on("metrics_collected")
    def _on_metrics_collected(ev):
        metrics.log_metrics(ev.metrics)
        usage_collector.collect(ev.metrics)

    async def log_usage():
        logger.info("Usage summary: %s", usage_collector.get_summary())

    ctx.add_shutdown_callback(log_usage)

    await session.start(agent=GameMasterAgent(universe="A coastal-fantasy island of broken lighthouses and sea-witches", tone="dramatic"), room=ctx.room,
                        room_input_options=RoomInputOptions(noise_cancellation=noise_cancellation.BVC()))
    await ctx.connect()


if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint, prewarm_fnc=prewarm))
