# agent.py - Voice Improv Battle Agent for Day 10
import logging
import os
import json
import random
from typing import Optional, List, Dict, Any

from dotenv import load_dotenv
from livekit.agents import (
    Agent,
    AgentSession,
    JobContext,
    JobProcess,
    RunContext,
    cli,
    MetricsCollectedEvent,
    RoomInputOptions,
    WorkerOptions,
    metrics,
    tokenize,
    function_tool,
)
from livekit.plugins import murf, silero, google, deepgram, noise_cancellation
from livekit.plugins.turn_detector.multilingual import MultilingualModel

logger = logging.getLogger("improv_agent")

load_dotenv(".env.local")

# ---------- Improv Scenarios ---------- #

IMPROV_SCENARIOS = [
    {
        "id": 1,
        "scenario": "You're a barista who has to tell a customer that their latte is actually a portal to another dimension.",
        "category": "fantasy"
    },
    {
        "id": 2,
        "scenario": "You're a time-traveling tour guide explaining modern smartphones to someone from the 1800s.",
        "category": "sci-fi"
    },
    {
        "id": 3,
        "scenario": "You're a restaurant waiter who must calmly tell a customer that their order has escaped the kitchen.",
        "category": "comedy"
    },
    {
        "id": 4,
        "scenario": "You're trying to return an obviously cursed object to a very skeptical shop owner.",
        "category": "fantasy"
    },
    {
        "id": 5,
        "scenario": "You're a weather reporter who realizes they can actually control the weather with their words.",
        "category": "superhero"
    }
]

# ---------- Murf TTS ---------- #

TTS_HOST = murf.TTS(
    voice="en-US-matthew",
    style="Story",
    tokenizer=tokenize.basic.SentenceTokenizer(min_sentence_len=2),
    text_pacing=True,
)

# ---------- Improv Battle Agent ---------- #

class ImprovBattleAgent(Agent):
    """
    Voice Improv Battle Game Host
    """

    def __init__(self, **kwargs):
        instructions = """You are the host of "Improv Battle" - a high-energy TV improv show!

PERSONA:
- Energetic, witty, and charismatic game show host
- Mix of supportive and honest critique
- Light teasing is allowed but always respectful
- Provide varied reactions: sometimes amused, sometimes critical, sometimes impressed

GAME FLOW:
1. Welcome the contestant and explain the rules
2. Present improv scenarios one by one
3. After each scene, give specific feedback
4. End with a fun summary of their performance

REACTION STYLE:
- Be specific about what worked or didn't
- Mix positive and constructive feedback
- Keep reactions engaging and entertaining
- Always maintain a fun, game-like atmosphere

Use the provided tools to manage game state and scenarios."""
        super().__init__(instructions=instructions, tts=TTS_HOST, **kwargs)

    async def on_enter(self) -> None:
        # Initialize game state
        game_state = _ensure_game_state(self.session)
        game_state.update({
            "current_round": 0,
            "max_rounds": 3,
            "phase": "intro",
            "rounds": [],
            "player_name": "Contestant"
        })

        await self.session.generate_reply(
            instructions=(
                "Welcome the contestant to Improv Battle with high energy! "
                "Explain that they'll face 3 improv scenarios and you'll be their host. "
                "Keep it fun and exciting. Ask for their name to start."
            )
        )

    # ---------- Game Management Tools ---------- #

    @function_tool()
    async def start_game(self, context: RunContext, player_name: str) -> str:
        """Start the improv battle game with player name"""
        session = context.session
        game_state = _ensure_game_state(session)

        game_state["player_name"] = player_name
        game_state["phase"] = "playing"

        return f"Welcome {player_name}! Let's start Improv Battle! Get ready for your first scenario..."

    @function_tool()
    async def get_next_scenario(self, context: RunContext) -> str:
        """Get the next improv scenario for the current round"""
        session = context.session
        game_state = _ensure_game_state(session)

        if game_state["current_round"] >= game_state["max_rounds"]:
            return "Game completed! No more scenarios."

        # Get random scenario
        available_scenarios = [s for s in IMPROV_SCENARIOS if s["id"] not in [r.get("scenario_id") for r in game_state["rounds"]]]
        if not available_scenarios:
            available_scenarios = IMPROV_SCENARIOS

        scenario = random.choice(available_scenarios)
        game_state["current_scenario"] = scenario

        return f"Round {game_state['current_round'] + 1}: {scenario['scenario']} Action!"

    @function_tool()
    async def submit_improv(self, context: RunContext, performance: str) -> str:
        """Submit player's improv performance and get host reaction"""
        session = context.session
        game_state = _ensure_game_state(session)

        if not game_state.get("current_scenario"):
            return "No active scenario! Please start a round first."

        # Generate varied host reaction
        reactions = [
            "That was hilarious! I loved how you committed to the character.",
            "Interesting choice! The premise was creative but could use more emotional range.",
            "Wow, you really went for it! The absurdity was perfectly balanced.",
            "Good effort! The scene felt a bit rushed - try to build more tension next time.",
            "Brilliant! Your timing and character work were spot on.",
            "Creative approach! Though I wish you'd explored the scenario's potential more."
        ]

        reaction = random.choice(reactions)

        # Record the round
        game_state["rounds"].append({
            "scenario_id": game_state["current_scenario"]["id"],
            "scenario": game_state["current_scenario"]["scenario"],
            "reaction": reaction
        })

        game_state["current_round"] += 1
        game_state["current_scenario"] = None

        if game_state["current_round"] >= game_state["max_rounds"]:
            game_state["phase"] = "completed"
            return f"{reaction} And that completes all 3 rounds! Let me give you your final summary..."
        else:
            return f"{reaction} Great job! Ready for your next challenge?"

    @function_tool()
    async def get_final_summary(self, context: RunContext) -> str:
        """Get final summary of player's performance"""
        session = context.session
        game_state = _ensure_game_state(session)

        strengths = [
            "amazing character work",
            "quick wit and timing", 
            "creative scenario exploration",
            "emotional range",
            "absurd humor",
            "commitment to the premise"
        ]

        player_strengths = random.sample(strengths, 2)

        return (f"What a performance, {game_state['player_name']}! "
                f"You showed incredible {player_strengths[0]} and {player_strengths[1]}. "
                f"Thanks for playing Improv Battle!")

    @function_tool()
    async def end_game(self, context: RunContext) -> str:
        """End the game session"""
        session = context.session
        game_state = _ensure_game_state(session)
        game_state["phase"] = "ended"

        return "Thanks for playing Improv Battle! Hope you had fun!"

# ---------- Game State Helpers ---------- #

def _ensure_game_state(session) -> Dict[str, Any]:
    """Ensure game state exists in session userdata"""
    ud = session.userdata
    game = ud.get("improv_game")
    if not isinstance(game, dict):
        game = {}
        ud["improv_game"] = game
    return game

# ---------- Prewarm ---------- #

def prewarm(proc: JobProcess):
    proc.userdata["vad"] = silero.VAD.load()

# ---------- Entrypoint ---------- #

async def entrypoint(ctx: JobContext):
    ctx.log_context_fields = {"room": ctx.room.name}

    session = AgentSession(
        stt=deepgram.STT(model="nova-3"),
        llm=google.LLM(model="gemini-2.5-flash"),
        tts=TTS_HOST,
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
        agent=ImprovBattleAgent(),
        room=ctx.room,
        room_input_options=RoomInputOptions(
            noise_cancellation=noise_cancellation.BVC(),
        ),
    )

    await ctx.connect()

if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint, prewarm_fnc=prewarm))