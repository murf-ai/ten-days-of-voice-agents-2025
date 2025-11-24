# backend/src/agent.py
import logging
import json
import os
import time
from datetime import datetime, timezone
from dotenv import load_dotenv
from pydantic import BaseModel
from typing import List, Optional

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
logger.setLevel(logging.INFO)

load_dotenv(".env.local")

# File where check-ins are stored
LOG_PATH = "wellness_log.json"


class WellnessAgent(Agent):
    def _init_(self) -> None:
        # System prompt: grounded, supportive, short, and safe
        super()._init_(
            instructions="""
You are a grounded, supportive health & wellness companion. You are empathetic, concise,
non-judgmental, and explicitly not a clinician. You will ask short daily check-in questions
and help the user set 1-3 small, realistic intentions for the day.

Behavior:
- Ask about mood and energy: e.g., "How are you feeling today?" "What's your energy like?"
- Ask for 1-3 intentions/objectives for the day and any small self-care plan.
- Offer short, actionable suggestions (e.g., break large tasks into small steps, take a 5-minute walk, short breathing break).
- Avoid medical or diagnostic wording.
- Confirm back: repeat the mood summary and the main objectives and ask "Does this sound right?"
- When you have mood, energy, and objectives, call the tool save_checkin(mood, energy, objectives) exactly once.
- If historical data is available, briefly reference the most recent previous check-in early in the conversation (e.g., "Last time you mentioned low energy; how is today compared to that?").
            """,
        )


class Checkin(BaseModel):
    timestamp: str
    mood: str
    energy: str
    objectives: List[str]
    agent_summary: Optional[str] = None


def _ensure_log():
    # Create file if missing with empty list
    if not os.path.exists(LOG_PATH):
        with open(LOG_PATH, "w", encoding="utf-8") as f:
            json.dump([], f)


def load_all_checkins() -> List[dict]:
    _ensure_log()
    with open(LOG_PATH, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except Exception:
            return []


def latest_checkin() -> Optional[dict]:
    entries = load_all_checkins()
    if not entries:
        return None
    # assume append order, return last
    return entries[-1]


@function_tool
async def save_checkin(ctx: RunContext, mood: str, energy: str, objectives: List[str]) -> str:
    """
    Save a wellness check-in to wellness_log.json and return a short agent summary.
    Called by the LLM when the check-in is complete.
    """
    _ensure_log()
    now = datetime.now(timezone.utc).isoformat()
    # Clean objectives and create summary
    obj_list = [o.strip() for o in objectives if o and o.strip()]
    summary = f"Reported mood: {mood}. Energy: {energy}. Objectives: {', '.join(obj_list) if obj_list else 'none'}."

    checkin = Checkin(
        timestamp=now,
        mood=mood,
        energy=energy,
        objectives=obj_list,
        agent_summary=summary,
    )

    # Append to JSON list
    entries = load_all_checkins()
    entries.append(checkin.model_dump())
    with open(LOG_PATH, "w", encoding="utf-8") as f:
        json.dump(entries, f, indent=2, ensure_ascii=False)

    logger.info(f"Saved checkin at {now}: {checkin.model_dump()}")

    # Short spoken summary for the agent to speak
    spoken = (
        f"Thanks — I've saved today's check-in. {summary} "
        f"I'll remember this and may reference it in future check-ins."
    )
    return spoken


def prewarm(proc: JobProcess):
    proc.userdata["vad"] = silero.VAD.load()


async def entrypoint(ctx: JobContext):
    # attach room to logs
    ctx.log_context_fields = {"room": ctx.room.name}

    # read latest checkin and place a small prompt hint in the session instructions by passing system context
    prev = latest_checkin()
    prev_hint = ""
    if prev:
        # safe brief reference to previous mood/energy
        pm = prev.get("mood", "")
        pe = prev.get("energy", "")
        prev_hint = f"Previous check-in: mood was '{pm}' and energy was '{pe}'. Refer to this once at the start."

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
        tools=[save_checkin],
    )

    # Metrics collection
    usage_collector = metrics.UsageCollector()

    @session.on("metrics_collected")
    def _on_metrics_collected(ev: MetricsCollectedEvent):
        metrics.log_metrics(ev.metrics)
        usage_collector.collect(ev.metrics)

    async def log_usage():
        s = usage_collector.get_summary()
        logger.info(f"Usage summary: {s}")

    ctx.add_shutdown_callback(log_usage)

    # Start session: we set a temporary assistant prompt via the agent class
    # If prev_hint exists, the session will have the agent instructions plus that hint
    if prev_hint:
        # Combine base instructions from WellnessAgent with prev_hint by making a new instance
        # (the Agent class already contains the main instructions; prev_hint will be available as context)
        logger.info(f"Passing previous check-in hint to session: {prev_hint}")

    await session.start(
        agent=WellnessAgent(),
        room=ctx.room,
        room_input_options=RoomInputOptions(noise_cancellation=noise_cancellation.BVC()),
    )

    # Connect and join
    await ctx.connect()


if _name_ == "_main_":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint, prewarm_fnc=prewarm))
