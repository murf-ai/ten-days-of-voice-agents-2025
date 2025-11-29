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
    WorkerOptions,
    RoomInputOptions,
    cli,
)

from livekit.plugins import (
    deepgram,
    google,
    murf,
    noise_cancellation,
    silero,
)
from livekit.plugins.turn_detector.multilingual import MultilingualModel


logger = logging.getLogger("game_master")
load_dotenv(".env.local")


# =====================================================
#       GAME MASTER AGENT (D&D STYLE)
# =====================================================

GAME_SYSTEM_PROMPT = """
You are a Game Master running a voice-only fantasy adventure.

RULES:
- Universe: Medieval fantasy world filled with dragons, magic, quests.
- Tone: Dramatic, immersive, adventurous.
- Role: You describe scenes, events, NPCs, and always ask: "What do you do?"
- Maintain continuity based on conversation history.
- Keep story moving forward through small narrative arcs.
- Do NOT give the player's actions yourself.
- Keep responses short (3–5 sentences max).
"""


class GameMasterAgent(Agent):

    def __init__(self):
        super().__init__(instructions=GAME_SYSTEM_PROMPT)
        self.sessions = {}

    async def on_join(self, ctx):
        sid = ctx.session.session_id

        self.sessions[sid] = {
            "story_started": False,
            "player_name": None
        }

        intro = (
            "Welcome, traveler. You stand at the edge of Eldoria, "
            "a land of lost kingdoms and ancient magic. Before we begin, "
            "what is your name, adventurer?"
        )
        await ctx.send_speech(intro)

    async def on_user_message(self, message, ctx):

        text = (message.text or "").strip()
        sid = ctx.session.session_id
        state = self.sessions[sid]

        # FIRST TIME PLAYER NAME
        if not state["story_started"]:
            state["player_name"] = text
            state["story_started"] = True

            opening_scene = (
                f"Ah, {state['player_name']}... a name sung in forgotten prophecies.\n"
                "Your journey begins on a misty trail leading into the Whispering Forest. "
                "You hear rustling behind you — and a glowing blue fox steps out.\n"
                "\"Do not be afraid,\" it says. \"Destiny has chosen you.\"\n"
                "What do you do?"
            )
            return await ctx.send_speech(opening_scene)

        # CONTINUE STORY USING LLM
        response = await ctx.session.llm.generate(
            messages=[
                {"role": "system", "content": GAME_SYSTEM_PROMPT},
                {"role": "user", "content": text}
            ]
        )

        gm_output = response.text.strip()

        # Ensure it ends with "What do you do?"
        if not gm_output.lower().strip().endswith("what do you do?"):
            gm_output += " What do you do?"

        await ctx.send_speech(gm_output)


# =====================================================
#       PREWARM VAD
# =====================================================
vad_model = silero.VAD.load()

def prewarm(proc: JobProcess):
    proc.userdata["vad"] = vad_model


# =====================================================
#       ENTRYPOINT
# =====================================================
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
        agent=GameMasterAgent(),
        room=ctx.room,
        room_input_options=RoomInputOptions(
            noise_cancellation=noise_cancellation.BVC()
        ),
    )
    await ctx.connect()


if __name__ == "__main__":
    cli.run_app(
        WorkerOptions(
            entrypoint_fnc=entrypoint,
            prewarm_fnc=prewarm,
        )
    )
