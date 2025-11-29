import logging
import json
import random
from dataclasses import dataclass, field, asdict
from typing import Optional, List, Dict, Any
from datetime import datetime

from dotenv import load_dotenv
from livekit.agents import (
    Agent,
    AgentSession,
    JobContext,
    JobProcess,
    MetricsCollectedEvent,
    WorkerOptions,
    cli,
    metrics,
    tokenize,
    function_tool,
    RunContext
)
from livekit.plugins import murf, silero, google, deepgram
from livekit.plugins.turn_detector.multilingual import MultilingualModel

logger = logging.getLogger("agent")
load_dotenv(".env.local")

# --- Game State Management ---
@dataclass
class PlayerCharacter:
    """Player's character stats."""
    name: str = "Hero"
    quirk_power: str = "Lightning Strike"  # Their special anime power
    health: int = 100
    energy: int = 100  # For using quirk powers
    strength: int = 10
    speed: int = 10
    intelligence: int = 10
    inventory: List[str] = field(default_factory=lambda: ["healing elixir", "training manual", "hero badge"])
    
    def is_alive(self) -> bool:
        return self.health > 0
    
    def can_use_quirk(self) -> bool:
        return self.energy >= 20

@dataclass
class GameState:
    """Tracks the game world state."""
    universe: str = "anime_hero_academy"
    current_location: str = "Hero Academy Training Grounds"
    player: PlayerCharacter = field(default_factory=PlayerCharacter)
    story_events: List[str] = field(default_factory=list)
    npcs_met: List[str] = field(default_factory=list)
    quests_active: List[str] = field(default_factory=lambda: ["Defeat the Shadow Demon terrorizing the village"])
    quests_completed: List[str] = field(default_factory=list)
    villains_defeated: List[str] = field(default_factory=list)
    turn_count: int = 0
    
    def add_event(self, event: str):
        """Add a story event."""
        self.story_events.append(event)
        self.turn_count += 1
    
    def meet_npc(self, npc_name: str):
        """Record meeting an NPC."""
        if npc_name not in self.npcs_met:
            self.npcs_met.append(npc_name)
    
    def defeat_villain(self, villain_name: str):
        """Record defeating a villain."""
        if villain_name not in self.villains_defeated:
            self.villains_defeated.append(villain_name)
    
    def complete_quest(self, quest: str):
        """Mark a quest as completed."""
        if quest in self.quests_active:
            self.quests_active.remove(quest)
            self.quests_completed.append(quest)

# --- Game Tools ---
@function_tool
async def roll_dice(
    context: RunContext,
    dice_type: str = "d20",
    modifier: int = 0
) -> str:
    """
    Roll dice for checks and challenges.
    
    Args:
        dice_type: Type of dice (d20, d6, d12)
        modifier: Modifier to add to the roll
    """
    dice_max = {
        "d20": 20,
        "d12": 12,
        "d10": 10,
        "d6": 6
    }.get(dice_type, 20)
    
    roll = random.randint(1, dice_max)
    total = roll + modifier
    
    result = "CRITICAL SUCCESS! ⚡" if roll == dice_max else "CRITICAL FAILURE! 💥" if roll == 1 else "SUCCESS! ✨" if total >= 15 else "PARTIAL SUCCESS" if total >= 10 else "FAILURE"
    
    return f"🎲 ROLL: {roll} (+ {modifier}) = {total} → {result}"

@function_tool
async def use_quirk_power(
    context: RunContext,
    power_description: str,
    target: str
) -> str:
    """
    Use the player's special anime quirk power.
    
    Args:
        power_description: Description of how the power is used
        target: What/who the power is aimed at
    """
    game: GameState = context.userdata["game_state"]
    
    if not game.player.can_use_quirk():
        return f"❌ EXHAUSTED: Not enough energy! Current energy: {game.player.energy}/100"
    
    # Use energy
    game.player.energy -= 20
    
    # Roll for power effectiveness
    roll = random.randint(1, 20)
    
    if roll >= 15:
        effect = "DEVASTATING! Your quirk power was incredibly effective! 💫"
    elif roll >= 10:
        effect = "EFFECTIVE! Your quirk power worked well! ⚡"
    else:
        effect = "WEAK! Your quirk power barely affected the target... 😓"
    
    context.userdata["game_state"] = game
    
    return f"⚡ QUIRK ACTIVATED: {game.player.quirk_power}! Energy: {game.player.energy}/100. {effect}"

@function_tool
async def update_player_health(
    context: RunContext,
    change: int,
    reason: str
) -> str:
    """
    Update player's health.
    
    Args:
        change: Health change (positive for healing, negative for damage)
        reason: Reason for the change
    """
    game: GameState = context.userdata["game_state"]
    
    old_health = game.player.health
    game.player.health = max(0, min(100, game.player.health + change))
    
    context.userdata["game_state"] = game
    
    if change > 0:
        return f"💚 HEALED: {old_health} → {game.player.health} HP ({reason})"
    else:
        if game.player.health <= 0:
            return f"💀 DEFEATED: Hero has fallen! ({reason}) GAME OVER..."
        elif game.player.health <= 20:
            return f"🩸 CRITICAL DAMAGE: {old_health} → {game.player.health} HP ({reason}). Warning: Very low health!"
        else:
            return f"💥 DAMAGED: {old_health} → {game.player.health} HP ({reason})"

@function_tool
async def restore_energy(
    context: RunContext,
    amount: int,
    method: str
) -> str:
    """
    Restore player's quirk energy.
    
    Args:
        amount: Energy to restore
        method: How energy is restored (rest, elixir, etc)
    """
    game: GameState = context.userdata["game_state"]
    
    old_energy = game.player.energy
    game.player.energy = min(100, game.player.energy + amount)
    
    context.userdata["game_state"] = game
    
    return f"⚡ ENERGY RESTORED: {old_energy} → {game.player.energy}/100 ({method})"

@function_tool
async def add_to_inventory(
    context: RunContext,
    item: str
) -> str:
    """
    Add an item to player's inventory.
    
    Args:
        item: Item to add
    """
    game: GameState = context.userdata["game_state"]
    game.player.inventory.append(item)
    context.userdata["game_state"] = game
    
    return f"🎁 ACQUIRED: {item}! Inventory: {', '.join(game.player.inventory)}"

@function_tool
async def use_item(
    context: RunContext,
    item: str
) -> str:
    """
    Use an item from inventory.
    
    Args:
        item: Item to use
    """
    game: GameState = context.userdata["game_state"]
    
    if item not in game.player.inventory:
        return f"❌ ERROR: {item} not in inventory"
    
    game.player.inventory.remove(item)
    
    # Handle item effects
    if "elixir" in item.lower() or "potion" in item.lower():
        heal = 30
        game.player.health = min(100, game.player.health + heal)
        result = f"💚 USED: {item}! Healed {heal} HP. Current: {game.player.health}/100"
    elif "energy" in item.lower():
        restore = 40
        game.player.energy = min(100, game.player.energy + restore)
        result = f"⚡ USED: {item}! Restored {restore} energy. Current: {game.player.energy}/100"
    else:
        result = f"✨ USED: {item}"
    
    context.userdata["game_state"] = game
    return result

@function_tool
async def change_location(
    context: RunContext,
    new_location: str,
    description: str
) -> str:
    """
    Move to a new location.
    
    Args:
        new_location: Name of the new location
        description: Brief description of the location
    """
    game: GameState = context.userdata["game_state"]
    old_location = game.current_location
    game.current_location = new_location
    game.add_event(f"Traveled to {new_location}")
    
    context.userdata["game_state"] = game
    
    return f"🌍 LOCATION: Now at {new_location}. {description}"

@function_tool
async def meet_character(
    context: RunContext,
    npc_name: str,
    npc_description: str
) -> str:
    """
    Introduce a new character.
    
    Args:
        npc_name: Name of the character
        npc_description: Brief description
    """
    game: GameState = context.userdata["game_state"]
    game.meet_npc(npc_name)
    game.add_event(f"Met {npc_name}")
    
    context.userdata["game_state"] = game
    
    return f"👤 CHARACTER MET: {npc_name} - {npc_description}"

@function_tool
async def defeat_villain(
    context: RunContext,
    villain_name: str
) -> str:
    """
    Record defeating a villain.
    
    Args:
        villain_name: Name of the villain
    """
    game: GameState = context.userdata["game_state"]
    game.defeat_villain(villain_name)
    game.add_event(f"Defeated {villain_name}")
    
    context.userdata["game_state"] = game
    
    return f"🏆 VICTORY: {villain_name} has been defeated! Villains defeated: {len(game.villains_defeated)}"

@function_tool
async def complete_quest(
    context: RunContext,
    quest_name: str
) -> str:
    """
    Mark a quest as completed.
    
    Args:
        quest_name: Name of the quest
    """
    game: GameState = context.userdata["game_state"]
    game.complete_quest(quest_name)
    
    context.userdata["game_state"] = game
    
    return f"✅ QUEST COMPLETE: {quest_name}! Quests remaining: {', '.join(game.quests_active) if game.quests_active else 'None - You are a true hero!'}"

@function_tool
async def check_status(
    context: RunContext
) -> str:
    """
    Check player's current status.
    """
    game: GameState = context.userdata["game_state"]
    
    status = f"""
📊 HERO STATUS:
🌍 Location: {game.current_location}
💚 Health: {game.player.health}/100
⚡ Energy: {game.player.energy}/100
⚡ Quirk: {game.player.quirk_power}
🎒 Inventory: {', '.join(game.player.inventory)}
📜 Active Quests: {', '.join(game.quests_active)}
🏆 Villains Defeated: {len(game.villains_defeated)}
"""
    return status.strip()

# --- Game Master Agent ---
class AnimeGameMaster(Agent):
    """Anime-style adventure game master."""
    
    def __init__(self, llm) -> None:
        super().__init__(
            instructions=(
                "You are an epic ANIME GAME MASTER running a shonen-style hero adventure! "
                "\n\n"
                "**UNIVERSE: Hero Academy - Anime Adventure**\n"
                "- Modern world where people have 'Quirks' (superpowers)\n"
                "- Player is a young hero-in-training with Lightning Strike quirk\n"
                "- Think: My Hero Academia meets Demon Slayer energy\n"
                "- Dramatic battles, character growth, intense emotions\n"
                "\n\n"
                "**ANIME TROPES TO USE:**\n"
                "- Power-up moments and dramatic reveals\n"
                "- Friendly rivals and wise mentors\n"
                "- Epic battle sequences with named attacks\n"
                "- Emotional backstories for villains\n"
                "- Training arcs and power progression\n"
                "- 'Believe in yourself!' themes\n"
                "\n\n"
                "**YOUR ROLE:**\n"
                "- Narrate like an anime episode\n"
                "- Use action sound effects (BOOM! SLASH! WHOOSH!)\n"
                "- Make battles dramatic and exciting\n"
                "- ALWAYS end with 'What do you do?'\n"
                "\n\n"
                "**GAME FLOW:**\n"
                "1. **Opening:** Hero receives urgent mission about Shadow Demon\n"
                "2. **Investigation:** Gather info, meet NPCs\n"
                "3. **Training:** Build up power if needed\n"
                "4. **Confrontation:** Epic battle with villain\n"
                "5. **Resolution:** Heroic victory!\n"
                "\n\n"
                "**TOOLS TO USE:**\n"
                "- roll_dice: For any action checks\n"
                "- use_quirk_power: When player uses their Lightning Strike\n"
                "- update_player_health: For damage in battles\n"
                "- restore_energy: After rest or using items\n"
                "- defeat_villain: When villain is beaten\n"
                "- change_location: Moving to new areas\n"
                "- meet_character: Introducing NPCs\n"
                "\n\n"
                "**LOCATIONS:** Training Grounds, Village, Dark Forest, Shadow Demon's Lair\n"
                "**CHARACTERS:** \n"
                "- Master Takeshi (wise mentor)\n"
                "- Sakura (rival hero-in-training)\n"
                "- Shadow Demon (main villain)\n"
                "- Lesser demons (minions)\n"
                "\n\n"
                "**CRITICAL RULES:**\n"
                "- Make it feel like an anime episode!\n"
                "- Use dramatic descriptions and sound effects\n"
                "- Call roll_dice before resolving risky actions\n"
                "- Make battles exciting with multiple exchanges\n"
                "- Encourage use of quirk powers\n"
                "- Session should last 8-15 exchanges\n"
                "\n\n"
                "START NOW: Set the opening scene with dramatic music energy! 🎌"
            ),
            tools=[
                roll_dice,
                use_quirk_power,
                update_player_health,
                restore_energy,
                add_to_inventory,
                use_item,
                change_location,
                meet_character,
                defeat_villain,
                complete_quest,
                check_status
            ],
            llm=llm
        )

# --- Entrypoint ---
async def entrypoint(ctx: JobContext):
    """Main entrypoint for anime game master."""
    
    # Initialize game state
    game_state = GameState()
    
    ctx.log_context_fields = {"room": ctx.room.name}
    llm = google.LLM(model="gemini-2.5-flash")
    
    session = AgentSession(
        stt=deepgram.STT(model="nova-3"),
        llm=llm,
        tts=murf.TTS(
            voice="en-US-ken",  # Dramatic voice for anime narrator
            style="Conversation",
            tokenizer=tokenize.basic.SentenceTokenizer(min_sentence_len=2),
            text_pacing=True
        ),
        turn_detection=MultilingualModel(),
        vad=silero.VAD.load(),
        preemptive_generation=True,
    )
    
    session.userdata = {"game_state": game_state}
    
    # Metrics
    usage_collector = metrics.UsageCollector()
    
    @session.on("metrics_collected")
    def _on_metrics_collected(ev: MetricsCollectedEvent):
        metrics.log_metrics(ev.metrics)
        usage_collector.collect(ev.metrics)
    
    async def log_usage():
        summary = usage_collector.get_summary()
        logger.info(f"Usage: {summary}")
        
        # Save game state
        final_state = session.userdata.get("game_state")
        if final_state:
            filename = f"anime_adventure_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            with open(filename, 'w') as f:
                json.dump(asdict(final_state), f, indent=2)
            logger.info(f"🎌 Anime adventure saved to {filename}")
    
    ctx.add_shutdown_callback(log_usage)
    
    # Start session
    await session.start(agent=AnimeGameMaster(llm=llm), room=ctx.room)
    await ctx.connect()

def prewarm(proc: JobProcess):
    """Preload resources."""
    pass

if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint, prewarm_fnc=prewarm))