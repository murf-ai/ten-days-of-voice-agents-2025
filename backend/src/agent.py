import json
import logging
from datetime import datetime
from pathlib import Path

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
)
from livekit.plugins import murf, deepgram, noise_cancellation, google, silero
from livekit.plugins.turn_detector.multilingual import MultilingualModel

logger = logging.getLogger("agent")
load_dotenv(".env.local")

# ---------------------------
# JSON LOG FILE
# ---------------------------
LOG_FILE = Path("wellness_log.json")


def load_logs():
    if LOG_FILE.exists():
        with open(LOG_FILE, "r") as f:
            return json.load(f)
    return []


def save_log(data):
    logs = load_logs()
    logs.append(data)
    with open(LOG_FILE, "w") as f:
        json.dump(logs, f, indent=4)
    logger.info("Saved wellness check-in to wellness_log.json")


# ---------------------------
# Health & Wellness State Machine
# ---------------------------
checkin_state = {
    "mood": "",
    "energy": "",
    "stress": "",
    "objectives": "",
    "selfcare": ""
}

questions = {
    "mood": "How are you feeling today?",
    "energy": "What’s your energy like today?",
    "stress": "Is anything stressing you out right now?",
    "objectives": "What are 1–3 things you’d like to get done today?",
    "selfcare": "Is there anything you want to do for yourself today? Maybe rest, exercise, or hobbies?"
}


def get_previous_reference():
    logs = load_logs()
    if not logs:
        return ""

    last = logs[-1]
    return f"Last time we talked, you mentioned feeling '{last['mood']}' with energy '{last['energy']}'. How does today compare?"


# ---------------------------
# Agent
# ---------------------------
class WellnessCompanion(Agent):
    def __init__(self):
        super().__init__(
            instructions="""
            You are a supportive, grounded health & wellness companion.
            You NEVER give medical advice or diagnoses.
            You help the user check in daily about their mood, energy, stress and simple goals.
            You give small, realistic, actionable advice only.
            After gathering all answers, you give a recap.
            """
        )

    async def on_join(self, context):
        reference = get_previous_reference()

        if reference:
            await context.send_speech(reference)

        # ask first unanswered field
        for field in checkin_state:
            if not checkin_state[field]:
                await context.send_speech(questions[field])
                break

    async def on_user_message(self, message, context):
        # find next unanswered field
        for field in checkin_state:
            if not checkin_state[field]:
                checkin_state[field] = message.text.strip()
                break

        # ask next unanswered field
        for next_field in checkin_state:
            if not checkin_state[next_field]:
                await context.send_speech(questions[next_field])
                return

        # If we reach here → all fields done
        recap = (
            f"Here's your check-in summary:\n"
            f"- Mood: {checkin_state['mood']}\n"
            f"- Energy: {checkin_state['energy']}\n"
            f"- Stress: {checkin_state['stress']}\n"
            f"- Objectives: {checkin_state['objectives']}\n"
            f"- Self-care plan: {checkin_state['selfcare']}\n\n"
            "Does this sound correct?"
        )

        await context.send_speech(recap)

        # Save data to JSON
        entry = {
            "datetime": datetime.now().isoformat(),
            "mood": checkin_state["mood"],
            "energy": checkin_state["energy"],
            "stress": checkin_state["stress"],
            "objectives": checkin_state["objectives"],
            "selfcare": checkin_state["selfcare"],
        }

        save_log(entry)


# ---------------------------
# Load VAD on main thread
# ---------------------------
vad_model = silero.VAD.load()


def prewarm(proc: JobProcess):
    proc.userdata["vad"] = vad_model


# ---------------------------
# Entrypoint
# ---------------------------
async def entrypoint(ctx: JobContext):
    ctx.log_context_fields = {"room": ctx.room.name}

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

    await session.start(
        agent=WellnessCompanion(),
        room=ctx.room,
        room_input_options=RoomInputOptions(
            noise_cancellation=noise_cancellation.BVC(),
        ),
    )

    await ctx.connect()


# ---------------------------
# Run Agent
# ---------------------------
if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint, prewarm_fnc=prewarm))
