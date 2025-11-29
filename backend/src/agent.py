
import logging
import json
import os
from datetime import datetime
from typing import Dict, Any, Optional, List

import asyncio
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

load_dotenv(dotenv_path=".env.local")
load_dotenv(dotenv_path=".env")


def build_system_prompt() -> str:
    return """
You are a Game Master (GM) running an interactive fantasy adventure in a world of dragons, magic, and medieval quests.
Your tone is dramatic and immersive, with a touch of humor to keep things engaging.

UNIVERSE:
- Classic fantasy kingdom: knights, wizards, dragons, elves, dwarves, ancient ruins.
- The player is a brave adventurer on a quest to defeat an evil sorcerer threatening the kingdom.

ROLE:
- You describe scenes vividly, narrate the story, and ask the player what they do next.
- ALWAYS end every response with a clear prompt for action, such as: "What do you do?" or "How do you respond?".
- Keep responses voice-friendly: natural, not too long, and engaging.

CONTINUITY:
- Maintain continuity using conversation history AND the JSON world state.
- Remember: player decisions, named characters, locations, quests, and consequences.
- If an NPC is dead in the world state, they must NOT suddenly appear alive.
- If the player has an item in inventory, you may reference it or let them use it.

WORLD STATE:
You have access to tools that manage a JSON world state representing characters, locations, events, and quests.

Tools:
1) get_world_state
   - Use this to inspect the current world state when you need to remember facts about the world,
     e.g., current location, quest status, inventory items, or NPCs.

2) update_world_state
   - Use this whenever the story changes something important:
     - Player HP changes (damage / healing).
     - Player inventory changes (items found, used, lost).
     - Location changes (moving to a new place).
     - NPCs created, befriended, angered, killed.
     - Quests or objectives started, progressed, or completed.
     - Major events (boss defeated, trap triggered, secret discovered).

UPDATE STRATEGY:
- Only include fields that changed in the updates payload.
- Prefer small, incremental updates instead of resending the whole world.
- Examples of valid updates:
  - {"locations": {"current": "Dark Forest", "visited": ["Village of Eldoria", "Dark Forest"]}}
  - {"characters": {"player": {"hp": 82, "inventory": ["sword", "shield", "healing potion"]}}}
  - {"events": ["Player entered the Dark Forest and heard distant growling."]}
  - {"quests": {"active": [{"id": "defeat_sorcerer", "completed_objectives": ["Find the sorcerer's lair"]}]}}

FLOW:
- On the first turn, start by setting up the scene in the Village of Eldoria and give the player 2–3 choices.
- Each turn:
  1) Optionally call get_world_state if you need to recall something.
  2) Interpret the player's action.
  3) If anything in the world changes, call update_world_state with a small JSON patch.
  4) Continue the story, moving toward a mini-arc (e.g., discovering a clue, surviving an ambush, or advancing the quest).
  5) Always end with a question: "What do you do?".

SESSION LENGTH:
- Aim for a short adventure of ~8–15 turns.
- It should reach at least one mini-arc: finding something valuable, escaping danger, defeating a threat, or making a key decision.
- When a mini-arc is completed, you may hint at future adventures but keep the current one reasonably self-contained.

STYLE:
- No markdown, no bullet lists, just spoken-style narration.
- Keep pacing tight, avoid walls of text.
"""


class GameMasterAgent(Agent):
    def __init__(self):
        print(">>> [AGENT INIT] Game Master Agent starting...")
        self.world_state = self.initialize_world_state()
        super().__init__(instructions=build_system_prompt())

    def initialize_world_state(self) -> Dict[str, Any]:
        """Initialize the world state with default values."""
        return {
            "characters": {
                "player": {
                    "name": "Adventurer",
                    "class": "Warrior",
                    "hp": 100,
                    "max_hp": 100,
                    "inventory": ["sword", "shield", "backpack"],
                    "traits": ["brave", "determined"],
                },
                "npcs": {
                    # will be filled as story goes on, e.g.:
                    # "village_elder": {"name": "Eldrin", "role": "Village Elder", "attitude": "friendly", "alive": True}
                },
            },
            "locations": {
                "current": "Village of Eldoria",
                "visited": ["Village of Eldoria"],
                "known_paths": {
                    "Village of Eldoria": ["Dark Forest", "Mountain Pass"],
                },
            },
            "events": [],
            "quests": {
                "active": [
                    {
                        "id": "defeat_sorcerer",
                        "title": "Defeat the Evil Sorcerer",
                        "description": "Find and defeat the sorcerer threatening the kingdom.",
                        "objectives": [
                            "Find the sorcerer's lair",
                            "Gather allies",
                            "Confront the sorcerer",
                        ],
                        "completed_objectives": [],
                    }
                ],
                "completed": [],
            },
        }

    def log_world_state(self):
        """Log the current world state for debugging."""
        logger.info("World State:\n%s", json.dumps(self.world_state, indent=2))

    async def on_enter(self) -> None:
        """
        Called when the agent becomes active in the session.
        Kick off the initial scene automatically.
        """
        logger.info(">>> [AGENT] on_enter – starting first scene")
        await self.session.generate_reply(
            instructions=(
                "Introduce the player in the Village of Eldoria at the start of their quest "
                "against the evil sorcerer. Describe the scene vividly and give them clear "
                "choices of what to do next. Always end with 'What do you do?'."
            )
        )

  

    @function_tool()
    async def get_world_state(self, ctx: RunContext) -> Dict[str, Any]:
        """
       Return the current JSON world state.

        Use this tool when you need to recall facts about the world such as:
        - current location,
        - visited locations,
        - player HP and inventory,
        - NPC status and attitudes,
        - quest objectives and progress.
        """
        # Just return the dict; LiveKit will serialize it.
        return self.world_state

    @function_tool()
    async def update_world_state(
        self, ctx: RunContext, updates: Dict[str, Any]
    ) -> str:
        """
        Update the world state with new information.

        Args:
            updates: A partial JSON object containing only the fields that changed.
                     Example:
                     {
                       "locations": {"current": "Dark Forest"},
                       "events": ["Player entered the Dark Forest"]
                     }

        The update will be applied as a deep merge into the existing world state.
        """
        if not isinstance(updates, dict):
            return "updates must be a JSON object"

        self._deep_update(self.world_state, updates)
        self.log_world_state()
        return "World state updated successfully."

    def _deep_update(self, base_dict: Dict[str, Any], update_dict: Dict[str, Any]):
        """Recursively update a dictionary in-place."""
        for key, value in update_dict.items():
            if (
                isinstance(value, dict)
                and key in base_dict
                and isinstance(base_dict[key], dict)
            ):
                self._deep_update(base_dict[key], value)
            else:
                base_dict[key] = value


def prewarm(proc: JobProcess):
    """Preload VAD model for faster startup."""
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

    # Connect to LiveKit room
    await ctx.connect()

    # Start the session with our Game Master
    await session.start(
        agent=GameMasterAgent(),
        room=ctx.room,
        room_input_options=RoomInputOptions(
            noise_cancellation=noise_cancellation.BVC(),
        ),
    )


if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint, prewarm_fnc=prewarm))
