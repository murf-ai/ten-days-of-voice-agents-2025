# IMPROVE THE AGENT AS PER YOUR NEED 1
"""
Day 8 – Voice Game Master (D&D-Style Adventure) - Voice-only GM agent

- Uses LiveKit agent plumbing similar to the provided food_agent_sqlite example.
- GM persona, universe, tone and rules are encoded in the agent instructions.
- Keeps STT/TTS/Turn detector/VAD integration untouched (murf, deepgram, silero, turn_detector).
- Tools:
    - start_adventure(): start a fresh session and introduce the scene
    - get_scene(): return the current scene description (GM text) ending with "What do you do?"
    - player_action(action_text): accept player's spoken action, update state, advance scene
    - show_journal(): list remembered facts, NPCs, named locations, choices
    - restart_adventure(): reset state and start over
- Userdata keeps continuity between turns: history, inventory, named NPCs/locations, choices, current_scene
"""

import json
import logging
import os
import asyncio
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Optional, Annotated

from dotenv import load_dotenv
from pydantic import Field
from livekit.agents import (
    Agent,
    AgentSession,
    JobContext,
    JobProcess,
    RoomInputOptions,
    WorkerOptions,
    cli,
    function_tool,
    RunContext,
)

from livekit.plugins import murf, silero, google, deepgram, noise_cancellation
from livekit.plugins.turn_detector.multilingual import MultilingualModel

# -------------------------
# Logging
# -------------------------
logger = logging.getLogger("voice_game_master")
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
logger.addHandler(handler)

load_dotenv(".env.local")

# -------------------------
# Simple Game World Definition
# -------------------------
# A compact world with a few scenes and choices forming a mini-arc.
WORLD = {
    "intro": {
        "title": "A Shadow over Brinmere",
        "desc": (
            "You awake on the damp shore of Brinmere, the moon a thin silver crescent. "
            "A ruined watchtower smolders a short distance inland, and a narrow path leads "
            "towards a cluster of cottages to the east. In the water beside you lies a "
            "small, carved wooden box, half-buried in sand."
        ),
        "choices": {
            "inspect_box": {
                "desc": "Inspect the carved wooden box at the water's edge.",
                "result_scene": "box",
            },
            "approach_tower": {
                "desc": "Head inland towards the smoldering watchtower.",
                "result_scene": "tower",
            },
            "walk_to_cottages": {
                "desc": "Follow the path east towards the cottages.",
                "result_scene": "cottages",
            },
        },
    },
    "box": {
        "title": "The Box",
        "desc": (
            "The box is warm despite the night air. Inside is a folded scrap of parchment "
            "with a hatch-marked map and the words: 'Beneath the tower, the latch sings.' "
            "As you read, a faint whisper seems to come from the tower, as if the wind "
            "itself speaks your name."
        ),
        "choices": {
            "take_map": {
                "desc": "Take the map and keep it.",
                "result_scene": "tower_approach",
                "effects": {"add_journal": "Found map fragment: 'Beneath the tower, the latch sings.'"},
            },
            "leave_box": {
                "desc": "Leave the box where it is.",
                "result_scene": "intro",
            },
        },
    },
    "tower": {
        "title": "The Watchtower",
        "desc": (
            "The watchtower's stonework is cracked and warm embers glow within. An iron "
            "latch covers a hatch at the base — it looks old but recently used. You can "
            "try the latch, look for other entrances, or retreat."
        ),
        "choices": {
            "try_latch_without_map": {
                "desc": "Try the iron latch without any clue.",
                "result_scene": "latch_fail",
            },
            "search_around": {
                "desc": "Search the nearby rubble for another entrance.",
                "result_scene": "secret_entrance",
            },
            "retreat": {
                "desc": "Step back to the shoreline.",
                "result_scene": "intro",
            },
        },
    },
    "tower_approach": {
        "title": "Toward the Tower",
        "desc": (
            "Clutching the map, you approach the watchtower. The map's marks align with "
            "the hatch at the base, and you notice a faint singing resonance when you step close."
        ),
        "choices": {
            "open_hatch": {
                "desc": "Use the map clue and try the hatch latch carefully.",
                "result_scene": "latch_open",
                "effects": {"add_journal": "Used map clue to open the hatch."},
            },
            "search_around": {
                "desc": "Search for another entrance.",
                "result_scene": "secret_entrance",
            },
            "retreat": {
                "desc": "Return to the shore.",
                "result_scene": "intro",
            },
        },
    },
    "latch_fail": {
        "title": "A Bad Twist",
        "desc": (
            "You twist the latch without heed — the mechanism sticks, and the effort sends "
            "a shiver through the ground. From inside the tower, something rustles in alarm."
        ),
        "choices": {
            "run_away": {
                "desc": "Run back to the shore.",
                "result_scene": "intro",
            },
            "stand_ground": {
                "desc": "Stand and prepare for whatever emerges.",
                "result_scene": "tower_combat",
            },
        },
    },
    "latch_open": {
        "title": "The Hatch Opens",
        "desc": (
            "With the map's guidance the latch yields and the hatch opens with a breath of cold air. "
            "Inside, a spiral of rough steps leads down into an ancient cellar lit by phosphorescent moss."
        ),
        "choices": {
            "descend": {
                "desc": "Descend into the cellar.",
                "result_scene": "cellar",
            },
            "close_hatch": {
                "desc": "Close the hatch and reconsider.",
                "result_scene": "tower_approach",
            },
        },
    },
    "secret_entrance": {
        "title": "A Narrow Gap",
        "desc": (
            "Behind a pile of rubble you find a narrow gap and old rope leading downward. "
            "It smells of cold iron and something briny."
        ),
        "choices": {
            "squeeze_in": {
                "desc": "Squeeze through the gap and follow the rope down.",
                "result_scene": "cellar",
            },
            "mark_and_return": {
                "desc": "Mark the spot and return to the shore.",
                "result_scene": "intro",
            },
        },
    },
    "cellar": {
        "title": "Cellar of Echoes",
        "desc": (
            "The cellar opens into a circular chamber where runes glow faintly. At the center "
            "is a stone plinth and upon it a small brass key and a sealed scroll."
        ),
        "choices": {
            "take_key": {
                "desc": "Pick up the brass key.",
                "result_scene": "cellar_key",
                "effects": {"add_inventory": "brass_key", "add_journal": "Found brass key on plinth."},
            },
            "open_scroll": {
                "desc": "Break the seal and read the scroll.",
                "result_scene": "scroll_reveal",
                "effects": {"add_journal": "Scroll reads: 'The tide remembers what the villagers forget.'"},
            },
            "leave_quietly": {
                "desc": "Leave the cellar and close the hatch behind you.",
                "result_scene": "intro",
            },
        },
    },
    "cellar_key": {
        "title": "Key in Hand",
        "desc": (
            "With the key in your hand the runes dim and a hidden panel slides open, revealing a "
            "small statue that begins to hum. A voice, ancient and kind, asks: 'Will you return what was taken?'"
        ),
        "choices": {
            "pledge_help": {
                "desc": "Pledge to return what was taken.",
                "result_scene": "reward",
                "effects": {"add_journal": "You pledged to return what was taken."},
            },
            "refuse": {
                "desc": "Refuse and pocket the key.",
                "result_scene": "cursed_key",
                "effects": {"add_journal": "You pocketed the key; a weight grows in your pocket."},
            },
        },
    },
    "scroll_reveal": {
        "title": "The Scroll",
        "desc": (
            "The scroll tells of an heirloom taken by a water spirit that dwells beneath the tower. "
            "It hints that the brass key 'speaks' when offered with truth."
        ),
        "choices": {
            "search_for_key": {
                "desc": "Search the plinth for a key.",
                "result_scene": "cellar_key",
            },
            "leave_quietly": {
                "desc": "Leave the cellar and keep the knowledge to yourself.",
                "result_scene": "intro",
            },
        },
    },
    "tower_combat": {
        "title": "Something Emerges",
        "desc": (
            "A hunched, brine-soaked creature scrambles out from the tower. Its eyes glow with hunger. "
            "You must act quickly."
        ),
        "choices": {
            "fight": {
                "desc": "Fight the creature.",
                "result_scene": "fight_win",
            },
            "flee": {
                "desc": "Flee back to the shore.",
                "result_scene": "intro",
            },
        },
    },
    "fight_win": {
        "title": "After the Scuffle",
        "desc": (
            "You manage to fend off the creature; it flees wailing towards the sea. On the ground lies "
            "a small locket engraved with a crest — likely the heirloom mentioned in the scroll."
        ),
        "choices": {
            "take_locket": {
                "desc": "Take the locket and examine it.",
                "result_scene": "reward",
                "effects": {"add_inventory": "engraved_locket", "add_journal": "Recovered an engraved locket."},
            },
            "leave_locket": {
                "desc": "Leave the locket and tend to your wounds.",
                "result_scene": "intro",
            },
        },
    },
    "reward": {
        "title": "A Minor Resolution",
        "desc": (
            "A small sense of peace settles over Brinmere. Villagers may one day know the heirloom is found, or it may remain a secret. "
            "You feel the night shift; the little arc of your story here closes for now."
        ),
        "choices": {
            "end_session": {
                "desc": "End the session and return to the shore (conclude mini-arc).",
                "result_scene": "intro",
            },
            "keep_exploring": {
                "desc": "Keep exploring for more mysteries.",
                "result_scene": "intro",
            },
        },
    },
    "cursed_key": {
        "title": "A Weight in the Pocket",
        "desc": (
            "The brass key glows coldly. You feel a heavy sorrow that tugs at your thoughts. "
            "Perhaps the key demands something in return..."
        ),
        "choices": {
            "seek_redemption": {
                "desc": "Seek a way to make amends.",
                "result_scene": "reward",
            },
            "bury_key": {
                "desc": "Bury the key and hope the weight fades.",
                "result_scene": "intro",
            },
        },
    },
}

# -------------------------
# Per-session Userdata
# -------------------------
@dataclass
class Userdata:
    player_name: Optional[str] = None
    current_scene: str = "intro"
    history: List[Dict] = field(default_factory=list)  # list of {'scene', 'action', 'time', 'result_scene'}
    journal: List[str] = field(default_factory=list)
    inventory: List[str] = field(default_factory=list)
    named_npcs: Dict[str, str] = field(default_factory=dict)
    choices_made: List[str] = field(default_factory=list)
    session_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    started_at: str = field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")

# -------------------------
# Helper functions
# -------------------------
def scene_text(scene_key: str, userdata: Userdata) -> str:
    """
    Build the descriptive text for the current scene, and append choices as short hints.
    Always end with 'What do you do?' so the voice flow prompts player input.
    """
    scene = WORLD.get(scene_key)
    if not scene:
        return "You are in a featureless void. What do you do?"

    desc = f"{scene['desc']}\n\nChoices:\n"
    for cid, cmeta in scene.get("choices", {}).items():
        desc += f"- {cmeta['desc']} (say: {cid})\n"
    # GM MUST end with the action prompt
    desc += "\nWhat do you do?"
    return desc

def apply_effects(effects: dict, userdata: Userdata):
    if not effects:
        return
    if "add_journal" in effects:
        userdata.journal.append(effects["add_journal"])
    if "add_inventory" in effects:
        userdata.inventory.append(effects["add_inventory"])
    # Extendable for more effect keys

def summarize_scene_transition(old_scene: str, action_key: str, result_scene: str, userdata: Userdata) -> str:
    """Record the transition into history and return a short narrative the GM can use."""
    entry = {
        "from": old_scene,
        "action": action_key,
        "to": result_scene,
        "time": datetime.utcnow().isoformat() + "Z",
    }
    userdata.history.append(entry)
    userdata.choices_made.append(action_key)
    return f"You chose '{action_key}'."

# -------------------------
# Agent Tools (function_tool)
# -------------------------

@function_tool
async def start_adventure(
    ctx: RunContext[Userdata],
    player_name: Annotated[Optional[str], Field(description="Player name", default=None)] = None,
) -> str:
    """Initialize a new adventure session for the player and return the opening description."""
    userdata = ctx.userdata
    if player_name:
        userdata.player_name = player_name
    userdata.current_scene = "intro"
    userdata.history = []
    userdata.journal = []
    userdata.inventory = []
    userdata.named_npcs = {}
    userdata.choices_made = []
    userdata.session_id = str(uuid.uuid4())[:8]
    userdata.started_at = datetime.utcnow().isoformat() + "Z"

    opening = (
        f"Greetings {userdata.player_name or 'traveler'}. Welcome to '{WORLD['intro']['title']}'.\n\n"
        + scene_text("intro", userdata)
    )
    # Ensure GM prompt present
    if not opening.endswith("What do you do?"):
        opening += "\nWhat do you do?"
    return opening

@function_tool
async def get_scene(
    ctx: RunContext[Userdata],
) -> str:
    """Return the current scene description (useful for 'remind me where I am')."""
    userdata = ctx.userdata
    scene_k = userdata.current_scene or "intro"
    txt = scene_text(scene_k, userdata)
    return txt

@function_tool
async def player_action(
    ctx: RunContext[Userdata],
    action: Annotated[str, Field(description="Player spoken action or the short action code (e.g., 'inspect_box' or 'take the box')")],
) -> str:
    """
    Accept player's action (natural language or action key), try to resolve it to a defined choice,
    update userdata, advance to the next scene and return the GM's next description (ending with 'What do you do?').
    """
    userdata = ctx.userdata
    current = userdata.current_scene or "intro"
    scene = WORLD.get(current)
    action_text = (action or "").strip()

    # Attempt 1: match exact action key (e.g., 'inspect_box')
    chosen_key = None
    if action_text.lower() in (scene.get("choices") or {}):
        chosen_key = action_text.lower()

    # Attempt 2: fuzzy match by checking if action_text contains the choice key or descriptive words
    if not chosen_key:
        # try to find a choice whose description words appear in action_text
        for cid, cmeta in (scene.get("choices") or {}).items():
            desc = cmeta.get("desc", "").lower()
            if cid in action_text.lower() or any(w in action_text.lower() for w in desc.split()[:4]):
                chosen_key = cid
                break

    # Attempt 3: fallback by simple keyword matching against choice descriptions
    if not chosen_key:
        for cid, cmeta in (scene.get("choices") or {}).items():
            for keyword in cmeta.get("desc", "").lower().split():
                if keyword and keyword in action_text.lower():
                    chosen_key = cid
                    break
            if chosen_key:
                break

    if not chosen_key:
        # If we still can't resolve, ask a clarifying GM response but keep it short and end with prompt.
        resp = (
            "I didn't quite catch that action for this situation. Try one of the listed choices or use a simple phrase like 'inspect the box' or 'go to the tower'.\n\n"
            + scene_text(current, userdata)
        )
        return resp

    # Apply the chosen choice
    choice_meta = scene["choices"].get(chosen_key)
    result_scene = choice_meta.get("result_scene", current)
    effects = choice_meta.get("effects", None)

    # Apply effects (inventory/journal, etc.)
    apply_effects(effects or {}, userdata)

    # Record transition
    _note = summarize_scene_transition(current, chosen_key, result_scene, userdata)

    # Update current scene
    userdata.current_scene = result_scene

    # Build narrative reply: echo a short confirmation, then describe next scene
    next_desc = scene_text(result_scene, userdata)

    # A small flourish so the GM sounds more persona-driven
    persona_pre = (
        "The Game Master (a calm, slightly mysterious narrator) replies:\n\n"
    )
    reply = f"{persona_pre}{_note}\n\n{next_desc}"
    # ensure final prompt present
    if not reply.endswith("What do you do?"):
        reply += "\nWhat do you do?"
    return reply

@function_tool
async def show_journal(
    ctx: RunContext[Userdata],
) -> str:
    userdata = ctx.userdata
    lines = []
    lines.append(f"Session: {userdata.session_id} | Started at: {userdata.started_at}")
    if userdata.player_name:
        lines.append(f"Player: {userdata.player_name}")
    if userdata.journal:
        lines.append("\nJournal entries:")
        for j in userdata.journal:
            lines.append(f"- {j}")
    else:
        lines.append("\nJournal is empty.")
    if userdata.inventory:
        lines.append("\nInventory:")
        for it in userdata.inventory:
            lines.append(f"- {it}")
    else:
        lines.append("\nNo items in inventory.")
    lines.append("\nRecent choices:")
    for h in userdata.history[-6:]:
        lines.append(f"- {h['time']} | from {h['from']} -> {h['to']} via {h['action']}")
    lines.append("\nWhat do you do?")
    return "\n".join(lines)

@function_tool
async def restart_adventure(
    ctx: RunContext[Userdata],
) -> str:
    """Reset the userdata and start again."""
    userdata = ctx.userdata
    userdata.current_scene = "intro"
    userdata.history = []
    userdata.journal = []
    userdata.inventory = []
    userdata.named_npcs = {}
    userdata.choices_made = []
    userdata.session_id = str(uuid.uuid4())[:8]
    userdata.started_at = datetime.utcnow().isoformat() + "Z"
    greeting = (
        "The world resets. A new tide laps at the shore. You stand once more at the beginning.\n\n"
        + scene_text("intro", userdata)
    )
    if not greeting.endswith("What do you do?"):
        greeting += "\nWhat do you do?"
    return greeting

# -------------------------
# The Agent (GameMasterAgent)
# -------------------------
class GameMasterAgent(Agent):
    def __init__(self):
        # System instructions define Universe, Tone, Role
        instructions = """
        You are 'Aurek', the Game Master (GM) for a voice-only, Dungeons-and-Dragons-style short adventure.
        Universe: Low-magic coastal fantasy (village of Brinmere, tide-smoothed ruins, minor spirits).
        Tone: Slightly mysterious, dramatic, empathetic (not overly scary).
        Role: You are the GM. You describe scenes vividly, remember the player's past choices, named NPCs, inventory and locations,
              and you always end your descriptive messages with the prompt: 'What do you do?'
        Rules:
            - Use the provided tools to start the adventure, get the current scene, accept the player's spoken action,
              show the player's journal, or restart the adventure.
            - Keep continuity using the per-session userdata. Reference journal items and inventory when relevant.
            - Drive short sessions (aim for several meaningful turns). Each GM message MUST end with 'What do you do?'.
            - Respect that this agent is voice-first: responses should be concise enough for spoken delivery but evocative.
        """
        super().__init__(
            instructions=instructions,
            tools=[start_adventure, get_scene, player_action, show_journal, restart_adventure],
        )

# -------------------------
# Entrypoint & Prewarm (keeps speech functionality)
# -------------------------
def prewarm(proc: JobProcess):
    # load VAD model and stash on process userdata, try/catch like original file
    try:
        proc.userdata["vad"] = silero.VAD.load()
    except Exception:
        logger.warning("VAD prewarm failed; continuing without preloaded VAD.")

async def entrypoint(ctx: JobContext):
    ctx.log_context_fields = {"room": ctx.room.name}
    logger.info("\n" + "🎲" * 8)
    logger.info("🚀 STARTING VOICE GAME MASTER (Brinmere Mini-Arc)")

    userdata = Userdata()

    session = AgentSession(
        stt=deepgram.STT(model="nova-3"),
        llm=google.LLM(model="gemini-2.5-flash"),
        tts=murf.TTS(
            voice="en-US-marcus",
            style="Conversational",
            text_pacing=True,
        ),
        turn_detection=MultilingualModel(),
        vad=ctx.proc.userdata.get("vad"),
        userdata=userdata,
    )

    # Start the agent session with the GameMasterAgent
    await session.start(
        agent=GameMasterAgent(),
        room=ctx.room,
        room_input_options=RoomInputOptions(noise_cancellation=noise_cancellation.BVC()),
    )

    await ctx.connect()

if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint, prewarm_fnc=prewarm))