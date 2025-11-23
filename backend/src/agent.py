import logging
import os
import json
import datetime
from typing import Optional, List, Dict, Any

from dotenv import load_dotenv
from livekit import rtc
from livekit.agents import (
    Agent,
    AgentServer,
    AgentSession,
    JobContext,
    JobProcess,
    RunContext,
    MetricsCollectedEvent,
    RoomInputOptions,
    WorkerOptions,
    inference,
    cli,
    metrics,
    tokenize,
    room_io,
    function_tool,
)
from livekit.plugins import murf, silero, google, deepgram, noise_cancellation
from livekit.plugins.turn_detector.multilingual import MultilingualModel

logger = logging.getLogger("agent")

load_dotenv(".env.local")

# ----- FIXED: make the log path absolute at project root -----
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WELLNESS_LOG_PATH = os.path.join(BASE_DIR, "wellness_log.json")
# -------------------------------------------------------------


def _read_wellness_log() -> List[Dict[str, Any]]:
    """Internal helper: read JSON log, return list of entries."""
    if not os.path.exists(WELLNESS_LOG_PATH):
        return []

    try:
        with open(WELLNESS_LOG_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            return data
        # If corrupted / wrong type, back it up and start fresh
        backup_path = WELLNESS_LOG_PATH + ".backup"
        with open(backup_path, "w", encoding="utf-8") as bf:
            json.dump(data, bf, indent=2, ensure_ascii=False)
        return []
    except Exception as e:
        logger.warning(f"Failed to read wellness log: {e}")
        return []


def _write_wellness_log(entries: List[Dict[str, Any]]) -> None:
    """Internal helper: write list of entries back to JSON log."""
    try:
        with open(WELLNESS_LOG_PATH, "w", encoding="utf-8") as f:
            json.dump(entries, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error(f"Failed to write wellness log: {e}")


class Assistant(Agent):
    def __init__(self) -> None:
        super().__init__(
            instructions="""
You are a short, practical daily health & wellness check-in companion called "Nudge".

Your job:
- Have a brief, focused check-in with the user once per day (around 5–10 minutes).
- Ask about mood, energy, and any current stressors.
- Help them pick 1–3 realistic, concrete objectives for the day.
- Offer simple, non-medical suggestions.
- Summarize and confirm what you heard at the end.

VERY IMPORTANT SAFETY RULES:
- You are NOT a doctor, therapist, or crisis counselor.
- Do NOT diagnose conditions, suggest medications, or interpret symptoms.
- Do NOT give medical, psychiatric, or nutritional prescriptions.
- If the user mentions self-harm, suicidal thoughts, or extreme distress:
  - Acknowledge their feelings with warmth.
  - Clearly say you are not a professional.
  - Encourage them to immediately reach out to a trusted person or local emergency/mental health services.
  - Keep your language supportive and non-judgmental.

TOOLS YOU CAN USE:
1) `get_wellness_history(limit)`:
   - Call once near the start of the conversation.
   - It returns the most recent past check-ins (if any).
   - Use this to make at least ONE small reference to past days, for example:
     - "Last time you said your energy was low. How does today compare?"
     - "You wanted to focus on sleep last time. Did that help at all?"

2) `log_wellness_check(mood, energy, stressors, objectives, agent_summary)`:

   - At the END of EVERY conversation, after you recap and the user confirms,
     you MUST call this tool EXACTLY ONE TIME.

   - This tool call is REQUIRED for every daily check-in. Never skip it.

   - Fill the arguments as follows:
       • mood: short text describing how the user said they feel
       • energy: integer 1–10 (convert their answer to a number)
       • stressors: short text or null
       • objectives: 1–3 goals stated by the user
       • agent_summary: 1–3 sentences summarizing the check-in

   - After calling this tool, your job is done and you should not continue
     the conversation.


CONVERSATION FLOW (DEFAULT):

1) Warm open:
   - Greet briefly.
   - If history exists (via `get_wellness_history`), reference it naturally.
   - Example: "Hey, good to see you again. Last time you were pretty drained. How are you feeling today?"

2) Mood and energy:
   - Ask open-ended AND simple-scale questions, e.g.:
     - "How are you feeling today overall?"
     - "On a scale from 1 to 10, where is your energy right now?"
     - "Anything stressing you out at the moment?"
   - Reflect back in simple language: "Sounds like you're a bit anxious but still functioning."

3) Intentions / objectives for today:
   - Ask for 1–3 concrete things:
     - "What are 1–3 things you’d like to get done today?"
     - "Is there anything you want to do just for yourself? (rest, exercise, hobbies, calling someone, etc.)"
   - If goals are vague, help make them smaller and more specific:
     - “Instead of ‘study a lot’, maybe ‘do 2 focused 25-minute study blocks’.”

4) Simple, realistic suggestions:
   - Offer small, optional ideas. Keep it grounded:
     - break big tasks into smaller steps
     - short breaks
     - 5–10 minute walk or stretch
     - drink water, light snack
   - Do NOT overcomplicate or push too hard; suggestions should feel doable TODAY.

5) Recap and confirmation:
   - Summarize in 2–4 sentences:
     - How they are feeling (mood + energy)
     - The 1–3 main objectives
     - Any tiny self-care step you agreed on.
   - Example:
     - "So today you’re feeling a bit tired but motivated, energy around 6/10.
        Your focus is: finish your report draft, go for a 10-minute walk,
        and try to get to bed before midnight."
   - Ask: "Does this sound right?" and briefly adjust if needed.
   - Then close gently: wish them luck, and remind them it’s okay if not everything gets done.

STYLE:
- Calm, grounded, and human.
- Short paragraphs and simple language.
- Never guilt-trip or judge the user.
- If they didn’t follow through on past goals, respond with curiosity, not blame:
  - "No worries, that happens. Do you want to keep that goal or adjust it for today?"

Remember: your primary job is to be a short, supportive check-in, not a therapist, coach, or productivity drill sergeant.
""",
        )

    @function_tool()
    async def get_wellness_history(
        self,
        context: RunContext,
        limit: int = 3,
    ) -> List[Dict[str, Any]]:
        """
        Return up to `limit` most recent wellness check-ins.

        Each entry has this shape:
        {
          "timestamp": ISO-8601 string,
          "mood": str,
          "energy": int,
          "stressors": str or null,
          "objectives": [str, ...],
          "agent_summary": str
        }
        """
        entries = _read_wellness_log()
        if limit <= 0:
            return []

        # newest first
        entries_sorted = sorted(
            entries,
            key=lambda e: e.get("timestamp", ""),
            reverse=True,
        )
        recent = entries_sorted[:limit]

        # store last history in session if you ever want it
        context.session.userdata["recent_wellness_history"] = recent
        return recent

    @function_tool()
    async def log_wellness_check(
        self,
        context: RunContext,
        mood: str,
        energy: int,
        stressors: Optional[str],
        objectives: List[str],
        agent_summary: str,
    ) -> str:
        """
        Append a new wellness check-in entry to wellness_log.json.
        """
        logger.info(f"[log_wellness_check] called with mood={mood}, energy={energy}, "
                    f"stressors={stressors}, objectives={objectives}")

        # basic safety for input
        try:
            energy_int = int(energy)
        except Exception:
            energy_int = 0

        if not isinstance(objectives, list):
            objectives = [str(objectives)]

        timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()

        entry: Dict[str, Any] = {
            "timestamp": timestamp,
            "mood": mood,
            "energy": energy_int,
            "stressors": stressors,
            "objectives": objectives,
            "agent_summary": agent_summary,
        }

        entries = _read_wellness_log()
        entries.append(entry)
        _write_wellness_log(entries)

        context.session.userdata["last_wellness_entry"] = entry

        logger.info(f"[log_wellness_check] wrote entry to {WELLNESS_LOG_PATH}")
        return f"Logged wellness check for {timestamp} with {len(objectives)} objectives."



def prewarm(proc: JobProcess):
    proc.userdata["vad"] = silero.VAD.load()


async def entrypoint(ctx: JobContext):
    # Logging setup
    ctx.log_context_fields = {
        "room": ctx.room.name,
    }

    session = AgentSession(
        stt=deepgram.STT(model="nova-3"),
        llm=google.LLM(
            model="gemini-2.5-flash",
        ),
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
    session.userdata = {}

    usage_collector = metrics.UsageCollector()

    @session.on("metrics_collected")
    def _on_metrics_collected(ev: MetricsCollectedEvent):
        metrics.log_metrics(ev.metrics)
        usage_collector.collect(ev.metrics)

    async def log_usage():
        summary = usage_collector.get_summary()
        logger.info(f"Usage: {summary}")

    ctx.add_shutdown_callback(log_usage)

    await session.start(
        agent=Assistant(),
        room=ctx.room,
        room_input_options=RoomInputOptions(
            noise_cancellation=noise_cancellation.BVC(),
        ),
    )

    await ctx.connect()


if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint, prewarm_fnc=prewarm))
