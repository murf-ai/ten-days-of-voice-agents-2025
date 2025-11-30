import logging
import json
import os
import random
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

logger = logging.getLogger("improv_battle_agent")
logging.basicConfig(level=logging.INFO)
load_dotenv(dotenv_path=".env.local")
load_dotenv(dotenv_path=".env")

# Data file paths
SCENARIOS_FILE = os.path.join(os.path.dirname(__file__), "../shared-data/day10_scenarios.json")

# Global state for current session
class ImprovGameState:
    def __init__(self):
        self.player_name = None
        self.current_round = 0
        self.max_rounds = 4  # 4 scenarios per game
        self.rounds = []  # list of {"scenario": str, "player_response": str, "host_reaction": str}
        self.phase = "intro"  # "intro" | "awaiting_improv" | "reacting" | "done"
        self.current_scenario = None
        self.scenarios_used = []
        self.all_scenarios = []
        self.improv_count = 0  # Counter to track how many times player has improvised

game_state = ImprovGameState()

def load_scenarios() -> List[Dict[str, Any]]:
    """Load improv scenarios from JSON file."""
    try:
        with open(SCENARIOS_FILE, "r") as f:
            data = json.load(f)
            return data.get("scenarios", [])
    except FileNotFoundError:
        logger.error(f"Scenarios file not found at {SCENARIOS_FILE}")
        return []

def get_random_scenario() -> Optional[Dict[str, Any]]:
    """Get a random scenario that hasn't been used yet this session."""
    available = [s for s in game_state.all_scenarios if s["id"] not in game_state.scenarios_used]
    if not available:
        # Reshuffle if all used
        game_state.scenarios_used = []
        available = game_state.all_scenarios
    
    if available:
        scenario = random.choice(available)
        game_state.scenarios_used.append(scenario["id"])
        return scenario
    return None

def build_system_prompt() -> str:
    return """
You are the energetic, witty host of "Improv Battle," a high-energy improv game show. Your role is to guide players through absurd and hilarious improv scenarios.

PERSONALITY:
- High-energy, enthusiastic, and comedic
- You're a seasoned improv show host with a sharp sense of humor
- You can be supportive, neutral, or mildly critical - but always constructive and respectful
- You genuinely enjoy when players do well, but you're not afraid to tease a bit
- You stay in character as the host throughout

SHOW STRUCTURE:
1. INTRO: Welcome the player warmly and explain the show format briefly
2. SCENARIOS: Run through improv scenarios one by one
3. REACTIONS: After each improv, react authentically - comment on what worked, what was funny, or what could improve
4. OUTRO: After all scenarios, give a brief summary of their performance as an improviser

DURING EACH ROUND:
1. You'll receive a scenario
2. You MUST clearly read the scenario to the player
3. You MUST explicitly tell them: "Alright, START IMPROVISING NOW!"
4. Wait for their response
5. Once they finish (indicated by pause, "end scene", or your judgement), react
6. Mix your reactions - sometimes positive, sometimes constructively critical, sometimes amused

REACTION STYLES (vary between these):
- SUPPORTIVE: "That was hilarious! The way you [specific detail] really sold it."
- CRITICAL-BUT-KIND: "That was good, but you could have leaned more into the character's emotions."
- SURPRISED: "Wow, I didn't see that coming! That was a bold choice."
- TEASING: "Okay, that was... interesting. Let's just say the pigeons might not approve!"
- MIXED: "I liked your energy, but maybe commit to the bit a little more."

IMPORTANT RULES:
- Keep host reactions SHORT and punchy (1-2 sentences max)
- Always move to the next scenario or outro smoothly
- Never make fun of the player personally - only react to their improv choices
- Stay respectful and fun
- If they say "stop game" or "end show", wrap up gracefully

TONE: Think of legendary improv hosts like Colin Mochrie or Aisha Tyler from "Whose Line Is It Anyway?" - quick-witted, supportive but not saccharine, and genuinely enjoying the chaos.
"""

class ImprovBattleAgent(Agent):
    def __init__(self):
        print(">>> [AGENT INIT] Improv Battle Host starting...")
        game_state.all_scenarios = load_scenarios()
        super().__init__(instructions=build_system_prompt())

    async def on_enter(self) -> None:
        """Called when agent starts - introduce the show."""
        logger.info(">>> [AGENT] on_enter – introducing Improv Battle")
        game_state.phase = "intro"
        await self.session.generate_reply(
            instructions=(
                "Welcome the player to 'Improv Battle'! Be high-energy and excited. Briefly explain that they'll go through "
                "several absurd scenarios and act them out, and you'll react and judge their improv. Ask for their name. "
                "Keep it under 30 seconds. End with something like: 'What's your name, my fellow improviser?'"
            )
        )

    @function_tool()
    async def set_player_name(self, ctx: RunContext, name: str) -> str:
        """
        Set the player's name.
        
        Args:
            name: The player's name
            
        Returns:
            Confirmation message
        """
        game_state.player_name = name
        logger.info(f"Player name set to: {name}")
        return f"Great to meet you, {name}! Let's start Improv Battle!"

    @function_tool()
    async def get_next_scenario(self, ctx: RunContext) -> Dict[str, Any]:
        """
        Get the next improv scenario for this round.
        
        Returns:
            Scenario object with id, title, and scenario text
        """
        if game_state.current_round >= game_state.max_rounds:
            return {"error": "Game over - all scenarios completed"}
        
        scenario = get_random_scenario()
        if not scenario:
            return {"error": "No scenarios available"}
        
        game_state.current_scenario = scenario
        game_state.phase = "awaiting_improv"
        game_state.improv_count = 0
        
        logger.info(f"Round {game_state.current_round + 1}: {scenario['title']}")
        
        return {
            "round": game_state.current_round + 1,
            "max_rounds": game_state.max_rounds,
            "title": scenario["title"],
            "scenario": scenario["scenario"],
        }

    @function_tool()
    async def improv_turn_completed(self, ctx: RunContext, user_response: Optional[str] = None) -> Dict[str, Any]:
        """
        Called when user finishes their improv for this scenario.
        Store their response and generate a host reaction.
        
        Args:
            user_response: Optional transcription of what the user said/did
            
        Returns:
            Host reaction and next steps
        """
        game_state.improv_count += 1
        
        if not game_state.current_scenario:
            return {"error": "No current scenario"}
        
        # Generate varied host reactions
        reaction_styles = [
            "That was hilarious! I loved the energy you brought.",
            "Interesting choices there. I appreciate the commitment to the bit!",
            "Okay, that was... something! Pretty creative, I'll give you that.",
            "Nice! You really leaned into the absurdity. Well done!",
            "That was wild! I didn't expect you to go in that direction, but respect.",
            "Good effort! You could have maybe held the character beat a little longer though.",
            "Wow, bold moves! Some landed better than others, but the confidence was there.",
            "That made me laugh! The way you handled that was genuinely funny.",
            "Alright, I see what you did there. A little rough around the edges, but creative!",
            "That's the improv spirit! Now THAT'S what I'm talking about!",
        ]
        
        host_reaction = random.choice(reaction_styles)
        
        game_state.rounds.append({
            "round": game_state.current_round + 1,
            "scenario_title": game_state.current_scenario["title"],
            "scenario_text": game_state.current_scenario["scenario"],
            "player_response": user_response or "[improvisation performed]",
            "host_reaction": host_reaction,
        })
        
        game_state.current_round += 1
        game_state.phase = "reacting"
        
        logger.info(f"Improv completed. Round score: {host_reaction}")
        
        if game_state.current_round >= game_state.max_rounds:
            return {
                "status": "round_complete",
                "reaction": host_reaction,
                "game_status": "finished",
                "message": "That was the last scenario!",
            }
        else:
            return {
                "status": "round_complete",
                "reaction": host_reaction,
                "game_status": "continuing",
                "next_round": game_state.current_round + 1,
                "message": f"Alright, ready for Round {game_state.current_round + 1}?",
            }

    @function_tool()
    async def end_game(self, ctx: RunContext) -> Dict[str, Any]:
        """
        End the game and provide a summary of the player's performance.
        
        Returns:
            Game summary and closing message
        """
        game_state.phase = "done"
        
        # Analyze performance for closing summary
        performance_summary = self._analyze_performance()
        
        return {
            "status": "game_ended",
            "player_name": game_state.player_name,
            "rounds_completed": game_state.current_round,
            "performance_analysis": performance_summary,
            "all_rounds": game_state.rounds,
        }

    def _analyze_performance(self) -> str:
        """Generate a performance summary based on reactions."""
        if not game_state.rounds:
            return "You showed great potential for an improviser!"
        
        summaries = [
            "You've got real comedic timing! Your characters were distinct and memorable.",
            "You're a natural at thinking on your feet. Some great moments in there!",
            "You showed good instincts for character work. Keep embracing the absurdity!",
            "You brought genuine energy to every scenario. That's the spirit of improv!",
            "You proved you can roll with the chaos. Nice work out there!",
            "You demonstrated flexibility and creativity. Those are the tools of great improvisers!",
        ]
        
        return random.choice(summaries)

    @function_tool()
    async def get_game_status(self, ctx: RunContext) -> Dict[str, Any]:
        """Get current game status."""
        return {
            "player_name": game_state.player_name,
            "current_round": game_state.current_round,
            "max_rounds": game_state.max_rounds,
            "phase": game_state.phase,
            "rounds_completed": len(game_state.rounds),
            "current_scenario": game_state.current_scenario["title"] if game_state.current_scenario else None,
        }


def prewarm(proc: JobProcess):
    """Preload VAD model for faster startup."""
    proc.userdata["vad"] = silero.VAD.load()


async def entrypoint(ctx: JobContext):
    print(">>> [BOOT] Improv Battle Agent starting...")
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
    
    # Start the session with our Improv Battle Host
    await session.start(
        agent=ImprovBattleAgent(),
        room=ctx.room,
        room_input_options=RoomInputOptions(
            noise_cancellation=noise_cancellation.BVC(),
        ),
    )


if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint, prewarm_fnc=prewarm))
