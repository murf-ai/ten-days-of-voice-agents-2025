import logging
import json
import os
from datetime import datetime
from typing import Annotated, Literal
from dataclasses import dataclass, field

from dotenv import load_dotenv
from pydantic import Field

from livekit.agents import (
    Agent,
    AgentSession,
    JobContext,
    JobProcess,
    RunContext,
    MetricsCollectedEvent,
    WorkerOptions,
    RoomInputOptions,
    cli,
    function_tool,
    metrics,
)

from livekit.plugins import murf, silero, google, deepgram, noise_cancellation
from livekit.plugins.turn_detector.multilingual import MultilingualModel

# --------------------------
# Load env
# --------------------------
load_dotenv(".env.local")
logger = logging.getLogger("agent")

# --------------------------
# Persistence helpers
# --------------------------
def get_logs_folder():
    base_dir = os.path.dirname(__file__)   # backend/src
    folder = os.path.join(base_dir, "logs")
    os.makedirs(folder, exist_ok=True)
    return folder

def get_log_path():
    return os.path.join(get_logs_folder(), "wellness_log.json")

def load_logs():
    path = get_log_path()
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r") as f:
            return json.load(f)
    except Exception:
        # if file corrupted, back it up and start fresh
        try:
            os.rename(path, path + ".bak")
        except Exception:
            pass
        return []

def append_log(entry: dict):
    logs = load_logs()
    logs.append(entry)
    with open(get_log_path(), "w") as f:
        json.dump(logs, f, indent=4)
    print("✅ Wellness entry saved:", entry.get("date"))

def get_last_entry():
    logs = load_logs()
    return logs[-1] if logs else None

# --------------------------
# Dataclasses / userdata
# --------------------------
@dataclass
class CheckInState:
    mood: str | None = None
    energy: str | None = None
    stress: str | None = None
    goals: list[str] = field(default_factory=list)
    confirmed: bool = False

    def is_complete(self) -> bool:
        # at least mood + energy + goals is expected
        return bool(self.mood and self.energy and len(self.goals) >= 1)

    def to_dict(self) -> dict:
        return {
            "mood": self.mood,
            "energy": self.energy,
            "stress": self.stress,
            "goals": self.goals,
            "confirmed": self.confirmed,
        }

@dataclass
class UserData:
    checkin: CheckInState

# --------------------------
# Tools (function_tool)
# --------------------------
@function_tool
async def set_mood(ctx: RunContext[UserData], mood: Annotated[str, Field(description="Short mood description")]):
    ctx.userdata.checkin.mood = mood.strip()
    return f"Got it — you feel '{ctx.userdata.checkin.mood}'. What's your energy like today (high / medium / low)?"

@function_tool
async def set_energy(ctx: RunContext[UserData], energy: Annotated[Literal["high", "medium", "low"], Field(description="Energy level")]):
    ctx.userdata.checkin.energy = energy
    return f"Energy noted as {energy}. Anything stressing you out right now? (optional)"

@function_tool
async def set_stress(ctx: RunContext[UserData], stress: Annotated[str, Field(description="Optional short stress note")] = None):
    ctx.userdata.checkin.stress = stress.strip() if stress else None
    return "Thanks — now, what are 1–3 small things you want to get done today? Say them separated by commas."

@function_tool
async def set_goals(ctx: RunContext[UserData], goals: Annotated[list[str], Field(description="List of 1-3 simple goals")] = None):
    # Normalize: strip and keep up to 3 goals
    parsed = []
    if isinstance(goals, list):
        parsed = [g.strip() for g in goals if g and g.strip()][:3]
    else:
        # fallback if model passes string: split by comma
        parsed = [g.strip() for g in (goals or "").split(",") if g.strip()][:3]
    ctx.userdata.checkin.goals = parsed
    return f"Nice — I got {len(parsed)} goal(s). Would you like a quick suggestion to make these easier to tackle?"

@function_tool
async def give_suggestion(ctx: RunContext[UserData], confirm: Annotated[Literal["yes", "no"], Field(description="User wants a suggestion or not")] = "yes"):
    # Simple, grounded suggestions based on energy
    energy = ctx.userdata.checkin.energy or "medium"
    suggestions = {
        "high": "You're energetic — try a focused 25-minute session on the most important task, then a 5-minute break.",
        "medium": "Do a 12-minute focused task, then a short walk or stretch for 3–5 minutes.",
        "low": "Pick one very small step (5–10 minutes) for a goal, and allow yourself a short rest afterwards."
    }
    if confirm == "yes":
        return suggestions.get(energy, suggestions["medium"])
    return "Okay — no suggestions. I'll summarize your check-in now."

@function_tool
async def complete_checkin(ctx: RunContext[UserData]):
    state = ctx.userdata.checkin
    if not state.is_complete():
        return "I don't have enough info yet — please tell me your mood, energy, and at least one goal."

    # Generate a short agent summary sentence
    summary_parts = []
    if state.mood:
        summary_parts.append(f"mood: {state.mood}")
    if state.energy:
        summary_parts.append(f"energy: {state.energy}")
    if state.goals:
        summary_parts.append(f"goals: {', '.join(state.goals)}")
    summary = " | ".join(summary_parts)

    entry = {
        "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "mood": state.mood,
        "energy": state.energy,
        "stress": state.stress,
        "goals": state.goals,
        "summary": summary
    }

    try:
        append_log(entry)
        state.confirmed = True
        return f"All set — I saved your check-in. Summary: {summary}"
    except Exception as e:
        return f"I saved locally but there was an issue writing to disk: {e}"

# --------------------------
# Agent persona
# --------------------------
class WellnessAgent(Agent):
    def __init__(self):
        super().__init__(
            instructions="""
You are a supportive, grounded daily wellness companion.
Do not provide medical advice or diagnosis.
Be brief, empathetic, and offer small actionable suggestions when appropriate.
Flow:
1) Ask mood, energy, optional stress.
2) Ask 1-3 small goals.
3) Offer a short suggestion if user wants.
4) Repeat a brief recap and confirm before saving.
""",
            tools=[set_mood, set_energy, set_stress, set_goals, give_suggestion, complete_checkin]
        )

# --------------------------
# Prewarm
# --------------------------
def prewarm(proc: JobProcess):
    proc.userdata["vad"] = silero.VAD.load()

# --------------------------
# Entrypoint
# --------------------------
async def entrypoint(ctx: JobContext):
    ctx.log_context_fields = {"room": ctx.room.name}
    print("\n" + "="*50)
    print("🫶 Wellness Companion Agent starting")
    print("📁 Log file:", get_log_path())
    print("="*50 + "\n")

    userdata = UserData(checkin=CheckInState())

    session = AgentSession(
        stt=deepgram.STT(model="nova-3"),
        llm=google.LLM(model="gemini-2.5-flash"),
        tts=murf.TTS(
            voice="en-US-matthew",
            style="Conversation",
            text_pacing=True,
        ),
        turn_detection=MultilingualModel(),
        vad=ctx.proc.userdata["vad"],
        userdata=userdata,
    )

    usage_collector = metrics.UsageCollector()

    @session.on("metrics_collected")
    def _on_metrics(ev: MetricsCollectedEvent):
        usage_collector.collect(ev.metrics)

    # Start session with the wellness agent
    await session.start(
        agent=WellnessAgent(),
        room=ctx.room,
        room_input_options=RoomInputOptions(
            noise_cancellation=noise_cancellation.BVC(),
        ),
    )

    # On connect, give a friendly opener referencing last entry if present
    last = get_last_entry()
    if last:
        opener = (
            f"Welcome back. Last time you said you felt '{last.get('mood')}' "
            f"with energy '{last.get('energy')}'. How are you feeling today?"
        )
    else:
        opener = "Hi — I'm your daily wellness companion. How are you feeling today?"

    await session.say(opener)

    # Connect to the room (keep running)
    await ctx.connect()

# --------------------------
# Run worker
# --------------------------
if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint, prewarm_fnc=prewarm))
