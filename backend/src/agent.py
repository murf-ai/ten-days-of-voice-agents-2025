# health_companion_agent.py
"""
Health & Wellness Voice Companion agent for LiveKit (Day 3)

Features implemented:
- Grounded system prompt for a supportive wellness companion (not clinical).
- Short voice check-ins that ask about mood, energy, stressors, and 1–3 simple intentions.
- Persists each check-in to a single JSON file (WELLNESS_LOG, default /tmp/wellness_log.json).
- Reads previous entries on startup and references the most recent entry in the conversation.
- Exposes a tool `update_wellness` which the assistant can call to save partial/final data.

Environment variables:
- WELLNESS_LOG: path to the JSON file used to persist check-ins (default: /tmp/wellness_log.json)
"""

import json
import logging
import os
from datetime import datetime
from typing import List, Optional, Dict, Any
from pathlib import Path
import tempfile

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

logger = logging.getLogger("health_agent")
load_dotenv(".env.local")

WELLNESS_LOG = os.environ.get("WELLNESS_LOG", "/tmp/wellness_log.json")


class Assistant(Agent):
    def __init__(self) -> None:
        # System prompt: grounded, non-diagnostic, supportive
        instructions = (
            "You are a friendly, grounding daily wellness companion. "
            "Your role is to check in briefly with the user about mood, energy, and 1–3 simple intentions for the day. "
            "Avoid any medical advice or diagnosis. Offer small, practical, non-clinical suggestions (e.g., take a 5-minute walk, break tasks into steps, short breathing). "
            "Persist key answers using the provided tool `update_wellness`. When referencing past sessions, be concise and empathetic (e.g., 'Last time you said you were low on energy... how does today compare?'). "
            "Close the check-in with a brief recap of mood and the 1–3 objectives and ask for confirmation."
        )
        super().__init__(instructions=instructions)

    @function_tool
    async def update_wellness(
        self,
        ctx: RunContext,
        mood_text: Optional[str] = None,
        mood_scale: Optional[int] = None,
        energy: Optional[str] = None,
        stressors: Optional[str] = None,
        objectives: Optional[List[str]] = None,
        finalize: Optional[bool] = False,
    ) -> Dict[str, Any]:
        """
        Tool the model calls to update/save the current wellness check-in state.
        If `finalize` is True, the entry is appended to the WELLNESS_LOG file and returns saved_path.
        The tool always returns the current partial state and, when final, the last saved entry.
        """
        proc: JobProcess = ctx.proc

        state = proc.userdata.get(
            "wellness_state",
            {
                "mood_text": "",
                "mood_scale": None,
                "energy": "",
                "stressors": "",
                "objectives": [],
                "created_at": None,
            },
        )

        # Update fields if provided
        if mood_text is not None:
            state["mood_text"] = str(mood_text).strip() if mood_text is not None else ""
        if mood_scale is not None:
            try:
                # coerce to int and clamp to 1..10
                m = int(mood_scale)
                if m < 1:
                    m = 1
                elif m > 10:
                    m = 10
                state["mood_scale"] = m
            except Exception:
                state["mood_scale"] = None
        if energy is not None:
            state["energy"] = str(energy).strip()
        if stressors is not None:
            state["stressors"] = str(stressors).strip()
        if objectives is not None:
            # accept either list or string (semicolon or comma separated)
            parsed: List[str] = []
            if isinstance(objectives, str):
                # split on semicolon or comma
                parts = [p.strip() for p in objectives.replace(";", ",").split(",") if p.strip()]
                parsed = parts[:3]
            elif isinstance(objectives, list):
                parsed = [str(o).strip() for o in objectives if str(o).strip()][:3]
            state["objectives"] = parsed

        # ensure created_at when first touched
        if not state.get("created_at"):
            state["created_at"] = datetime.utcnow().isoformat() + "Z"

        proc.userdata["wellness_state"] = state

        response: Dict[str, Any] = {"state": state, "finalized": False}

        if finalize:
            entry = _make_entry_from_state(state, proc)
            try:
                saved_path = _append_entry_to_log(entry)
                proc.userdata.pop("wellness_state", None)
                response.update({"finalized": True, "entry": entry, "saved_path": saved_path})
            except Exception as e:
                logger.exception("Failed to finalize and append wellness entry.")
                response.update({"finalized": False, "error": str(e)})

        return response


def _make_entry_from_state(state: dict, proc: JobProcess) -> dict:
    entry = {
        "timestamp_utc": datetime.utcnow().isoformat() + "Z",
        "mood_text": state.get("mood_text"),
        "mood_scale": state.get("mood_scale"),
        "energy": state.get("energy"),
        "stressors": state.get("stressors"),
        "objectives": state.get("objectives", []),
        "agent_summary": _agent_summary(state),
        "room": getattr(proc, "room", None).name if getattr(proc, "room", None) else None,
    }
    return entry


def _agent_summary(state: dict) -> str:
    mood_text = state.get("mood_text")
    mood_scale = state.get("mood_scale")
    if mood_text:
        mood = mood_text
    elif mood_scale is not None:
        mood = f"mood scale {mood_scale}"
    else:
        mood = "unspecified mood"
    objs = state.get("objectives") or []
    objs_text = ", ".join(objs[:3]) if objs else "no objectives stated"
    return f"Mood: {mood}. Objectives: {objs_text}."


def _append_entry_to_log(entry: dict) -> str:
    """
    Append an entry to WELLNESS_LOG safely (atomic replace).
    Returns absolute path to the log file.
    """
    path = Path(WELLNESS_LOG)
    # Create parent directory if necessary
    if path.parent and not path.parent.exists():
        path.parent.mkdir(parents=True, exist_ok=True)

    data = []
    if path.exists():
        try:
            with path.open("r", encoding="utf-8") as f:
                data = json.load(f)
                if not isinstance(data, list):
                    logger.warning("Wellness log existed but was not a list; resetting to empty list.")
                    data = []
        except Exception as e:
            logger.warning(f"Could not read wellness log (will reset): {e}")
            data = []

    data.append(entry)

    # Write atomically: write to temp file then replace
    dir_for_temp = path.parent if path.parent.exists() else Path(tempfile.gettempdir())
    fd, tmp_path = tempfile.mkstemp(dir=str(dir_for_temp))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as tmpf:
            json.dump(data, tmpf, ensure_ascii=False, indent=2)
            tmpf.flush()
            os.fsync(tmpf.fileno())
        os.replace(tmp_path, str(path))
        logger.info(f"Appended wellness entry to {path}")
    except Exception as e:
        # Clean up temp file on failure
        try:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        except Exception:
            pass
        logger.exception(f"Failed to write wellness log: {e}")
        raise

    return str(path.resolve())


def _load_wellness_log() -> List[dict]:
    path = Path(WELLNESS_LOG)
    if not path.exists():
        return []
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, list):
                return data
            logger.warning("Wellness log JSON exists but is not a list; returning empty list.")
    except Exception as e:
        logger.warning(f"Failed to load wellness log: {e}")
    return []


def prewarm(proc: JobProcess):
    # Load VAD once per worker and store in proc.userdata
    proc.userdata["vad"] = silero.VAD.load()


async def entrypoint(ctx: JobContext):
    ctx.log_context_fields = {"room": ctx.room.name}

    # Ensure the worker has access to prior log and make a light reference available
    previous = _load_wellness_log()
    ctx.proc.userdata["wellness_log"] = previous
    if previous:
        ctx.proc.userdata["last_entry"] = previous[-1]

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

    # Start the session with the Assistant. The assistant's instructions encourage it to reference last_entry if present.
    await session.start(
        agent=Assistant(),
        room=ctx.room,
        room_input_options=RoomInputOptions(noise_cancellation=noise_cancellation.BVC()),
    )

    await ctx.connect()


if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint, prewarm_fnc=prewarm))
