# Day 4 – Teach-the-Tutor: Active Recall Coach

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

# -----------------------------------------
# Load Tutor Content
# -----------------------------------------
CONTENT_FILE = Path("shared-data/day4_tutor_content.json")

def load_content():
    if CONTENT_FILE.exists():
        with open(CONTENT_FILE, "r") as f:
            return json.load(f)
    return []

content = load_content()

# -----------------------------------------
# Tutor State
# -----------------------------------------
tutor_state = {
    "mode": None,          # learn | quiz | teach_back
    "current": None,       # concept id
}

VOICE_MAP = {
    "learn": {"voice": "Matthew", "model": "en-US-matthew"},
    "quiz": {"voice": "Alicia", "model": "en-US-alicia"},
    "teach_back": {"voice": "Ken", "model": "en-US-ken"},
}

# -----------------------------------------
# Helpers
# -----------------------------------------
def get_concept(concept_id):
    for c in content:
        if c["id"] == concept_id:
            return c
    return None

# -----------------------------------------
# Agent Class
# -----------------------------------------
class TeachTheTutor(Agent):
    def __init__(self):
        super().__init__(
            instructions="""
            You are an Active Recall Tutor with three modes:
            1. learn – Explain concepts using the JSON file.
            2. quiz – Ask questions.
            3. teach_back – Ask user to explain the concept back.

            Always follow the current mode and use the content file.
            User can switch modes anytime by saying switch to learn/quiz/teach back.

            Greets user and asks which mode they want.
            """
        )

    async def on_join(self, context):
        await context.send_speech(
            "Hello! I'm your Active Recall Coach. Would you like to learn, be quizzed, or teach back a concept?"
        )

    async def on_user_message(self, message, context):
        msg = message.text.lower()

        # Mode switching
        if "learn" in msg:
            tutor_state["mode"] = "learn"
            await context.send_speech("Great, you're in Learn mode! Which concept? Variables or Loops?")
            return
        if "quiz" in msg:
            tutor_state["mode"] = "quiz"
            await context.send_speech("Okay! You're in Quiz mode. Which concept should I quiz you on?")
            return
        if "teach" in msg:
            tutor_state["mode"] = "teach_back"
            await context.send_speech("You're in Teach-Back mode! Which concept will you teach me?")
            return

        # Concept selection
        for c in content:
            if c["id"] in msg or c["title"].lower() in msg:
                tutor_state["current"] = c["id"]
                await self.process_concept(context)
                return

        # If already in mode + concept selected and user responded
        if tutor_state["mode"] == "quiz":
            await context.send_speech("Nice! Want another question or switch mode?")
            return

        if tutor_state["mode"] == "teach_back":
            await context.send_speech("Thanks for explaining! Your summary shows good understanding. Want to try another concept?")
            return

    async def process_concept(self, context):
        mode = tutor_state["mode"]
        concept = get_concept(tutor_state["current"])
        voice = VOICE_MAP[mode]["model"]

        # Switch TTS Voice
        context.session.set_tts(
            murf.TTS(
                voice=voice,
                style="Conversation",
                tokenizer=tokenize.basic.SentenceTokenizer(min_sentence_len=2),
            )
        )

        if mode == "learn":
            await context.send_speech(f"Here's the concept: {concept['summary']}")
            await context.send_speech("Would you like to learn another concept or switch modes?")

        elif mode == "quiz":
            await context.send_speech(concept["sample_question"])

        elif mode == "teach_back":
            await context.send_speech(
                f"Okay, teach this back to me: {concept['sample_question']}"
            )

# -----------------------------------------
# Load VAD
# -----------------------------------------
vad_model = silero.VAD.load()

def prewarm(proc: JobProcess):
    proc.userdata["vad"] = vad_model

# -----------------------------------------
# Entrypoint
# -----------------------------------------
async def entrypoint(ctx: JobContext):
    session = AgentSession(
        stt=deepgram.STT(model="nova-3"),
        llm=google.LLM(model="gemini-2.5-flash"),
        tts=murf.TTS(voice="en-US-matthew", style="Conversation"),
        turn_detection=MultilingualModel(),
        vad=ctx.proc.userdata["vad"],
        preemptive_generation=True,
    )

    await session.start(
        agent=TeachTheTutor(),
        room=ctx.room,
        room_input_options=RoomInputOptions(noise_cancellation=noise_cancellation.BVC()),
    )

    await ctx.connect()


if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint, prewarm_fnc=prewarm))
