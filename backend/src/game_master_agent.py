import logging
import json
import uuid
import os
import asyncio
from datetime import datetime
from typing import Dict, Any, Optional, List
from dotenv import load_dotenv

from livekit.agents import (
    Agent,
    AgentSession,
    JobContext,
    JobProcess,
    RoomInputOptions,
    WorkerOptions,
    cli,
    tokenize,
    function_tool,
    RunContext,
)
from livekit.plugins import murf, silero, google, deepgram, noise_cancellation
from livekit.plugins.turn_detector.multilingual import MultilingualModel

logger = logging.getLogger("game_master_agent")
logging.basicConfig(level=logging.INFO)

load_dotenv(".env")


def build_system_prompt() -> str:
    return """
You are a Game Master (GM) running an interactive fantasy adventure in a world of dragons, magic, and medieval quests.
Your tone is dramatic and immersive, with a touch of humor to keep things engaging.

Role: You describe scenes vividly, narrate the story, and ask the player what they do next. Always end your responses with a question like "What do you do?" to prompt the player's action.

Universe: A classic fantasy setting with knights, wizards, dragons, elves, dwarves, and ancient ruins. The player is a brave adventurer on a quest to defeat an evil sorcerer threatening the kingdom.

Maintain continuity: Remember past decisions, locations, characters, and events from the conversation history. Build on previous actions to create a cohesive story.

Drive the story: Keep the adventure moving with challenges, discoveries, and choices. Aim for a short session with 8-15 exchanges, reaching a mini-arc like finding a treasure, escaping danger, or completing a quest.

Be voice-friendly: Responses should be natural for speech, not too long, and engaging.
"""


class GameMasterAgent(Agent):
    def __init__(self):
        print(">>> [AGENT INIT] Game Master Agent starting...")
        super().__init__(instructions=build_system_prompt())


def prewarm(proc: JobProcess):
    proc.userdata["vad"] = silero.VAD.load()


async def entrypoint(ctx: JobContext):
    print(">>> [BOOT] Game Master Agent starting...")

    vad = ctx.proc.userdata["vad"]

    session = AgentSession(
        stt=deepgram.STT(model="nova-3"),
        llm=google.LLM(model="gemini-2.5-flash"),
        tts=murf.TTS(
            voice="en-US-ken",
            style="Conversation",
            tokenizer=tokenize.basic.SentenceTokenizer(min_sentence_len=2),
            text_pacing=True,
        ),
        turn_detection=MultilingualModel(),
        vad=vad,
        preemptive_generation=True,
    )

    await ctx.connect()

    await session.start(
        agent=GameMasterAgent(),
        room=ctx.room,
        room_input_options=RoomInputOptions(
            noise_cancellation=noise_cancellation.BVC(),
        ),
    )


if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint, prewarm_fnc=prewarm))