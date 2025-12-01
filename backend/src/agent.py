import logging
import json
from pathlib import Path
from datetime import datetime
from typing import Annotated
import random

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
    function_tool,
    RunContext,
)
from livekit.plugins import murf, silero, google, deepgram, noise_cancellation
from livekit.plugins.turn_detector.multilingual import MultilingualModel

logger = logging.getLogger("agent")
logger.setLevel(logging.INFO)

load_dotenv(".env.local")

# Improv scenarios - Adult/Cinematic focused (generic descriptions)
SCENARIOS = [
    "You are a billionaire tech genius trying to convince your team that your latest invention is totally safe, despite it just exploding in the lab 5 minutes ago.",
    "You are a time-enforcement agent explaining to a confused person why their timeline is being erased and they need to come with you immediately.",
    "You are a master sorcerer negotiating with a dangerous villain to prevent them from destroying half the city, but you can only offer them a really disappointing compromise.",
    "You are a secret agency operative interrogating someone who claims they're from the future and knows about an alien invasion happening tomorrow.",
    "You are a young vigilante with a secret identity trying to explain to your boss why you're late again without revealing your double life.",
    "You are a brilliant scientist from an advanced hidden nation pitching revolutionary technology to the council, but it has one major embarrassing flaw.",
    "You are a smooth-talking trickster trying to charm your way out of trouble after getting caught scheming again.",
    "You are meeting an alternate version of yourself from another dimension and trying to convince them you're real and not just losing your mind.",
    "You are a gang leader in 1920s Birmingham trying to negotiate a dangerous deal with a rival family without starting a war.",
    "You are an astronaut trying to explain to mission control that you've discovered something impossible near a black hole, but they think your equipment is malfunctioning.",
    "You are a time-traveler from the future trying to warn someone about a catastrophic event tomorrow, but they think you're just a crazy conspiracy theorist.",
    "You are someone with severe anger issues trying to stay calm during an extremely frustrating situation while feeling yourself about to lose control.",
    "You are a mystical mentor trying to teach a skeptical student their first magic spell, but everything keeps going hilariously wrong.",
    "You are a one-eyed spy director trying to recruit someone for a top-secret mission, but you legally can't tell them any actual details about it.",
    "You are a master thief planning an elaborate heist with your crew, but your plan has one obvious flaw everyone keeps pointing out."
]

# Game state storage
GAME_SESSIONS = {}

# Session storage directory
SESSIONS_DIR = Path(__file__).parent.parent / "shared-data" / "improv_sessions"
SESSIONS_DIR.mkdir(parents=True, exist_ok=True)


def get_game_state(session_id: str) -> dict:
    """Get or create game state for a session"""
    if session_id not in GAME_SESSIONS:
        GAME_SESSIONS[session_id] = {
            "player_name": None,
            "current_round": 0,
            "max_rounds": 3,
            "rounds": [],
            "phase": "intro",
            "current_scenario": None,
            "session_start": datetime.now().isoformat()
        }
    return GAME_SESSIONS[session_id]


def save_session(session_id: str):
    """Save session to file"""
    try:
        state = GAME_SESSIONS.get(session_id)
        if state:
            filepath = SESSIONS_DIR / f"session_{session_id}.json"
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(state, f, indent=2, ensure_ascii=False)
            logger.info(f"Session {session_id} saved to {filepath}")
    except Exception as e:
        logger.error(f"Error saving session: {e}")


@function_tool()
async def start_game(
    context: RunContext,
    player_name: Annotated[str, "The player's name"]
) -> str:
    """Start the improv game with player name"""
    
    logger.info(f"=== start_game called ===")
    logger.info(f"Player name: {player_name}")
    
    try:
        session_id = context.agent_session.session_id
        state = get_game_state(session_id)
        
        state["player_name"] = player_name
        state["phase"] = "ready_for_scenario"
        
        save_session(session_id)
        
        return f"Great to have you here, {player_name}! Let me set up your first improv scenario."
        
    except Exception as e:
        logger.error(f"ERROR in start_game: {str(e)}", exc_info=True)
        return f"Error starting game: {str(e)}"


@function_tool()
async def next_scenario(context: RunContext) -> str:
    """Get the next improv scenario for the player"""
    
    logger.info(f"=== next_scenario called ===")
    
    try:
        session_id = context.agent_session.session_id
        state = get_game_state(session_id)
        
        if state["current_round"] >= state["max_rounds"]:
            return "game_complete"
        
        # Select random unused scenario
        used_scenarios = [r.get("scenario") for r in state["rounds"]]
        available = [s for s in SCENARIOS if s not in used_scenarios]
        
        if not available:
            available = SCENARIOS
        
        scenario = random.choice(available)
        
        state["current_round"] += 1
        state["current_scenario"] = scenario
        state["phase"] = "awaiting_improv"
        
        save_session(session_id)
        
        round_num = state["current_round"]
        return f"Round {round_num} of {state['max_rounds']}: {scenario} Go ahead and act it out!"
        
    except Exception as e:
        logger.error(f"ERROR in next_scenario: {str(e)}", exc_info=True)
        return f"Error getting scenario: {str(e)}"


@function_tool()
async def scene_complete(
    context: RunContext,
    performance_summary: Annotated[str, "Brief summary of what the player did in their improv"]
) -> str:
    """Mark scene as complete and generate host reaction"""
    
    logger.info(f"=== scene_complete called ===")
    logger.info(f"Performance summary: {performance_summary}")
    
    try:
        session_id = context.agent_session.session_id
        state = get_game_state(session_id)
        
        # Generate reaction tone (varied)
        reaction_styles = [
            "positive_enthusiastic",
            "positive_mild", 
            "critical_constructive",
            "mixed",
            "surprised"
        ]
        reaction_style = random.choice(reaction_styles)
        
        # Store round data
        round_data = {
            "round_number": state["current_round"],
            "scenario": state["current_scenario"],
            "performance_summary": performance_summary,
            "reaction_style": reaction_style
        }
        
        state["rounds"].append(round_data)
        state["phase"] = "reacting"
        
        save_session(session_id)
        
        # Return signal for host to generate appropriate reaction
        return f"reaction_needed|{reaction_style}|{performance_summary}"
        
    except Exception as e:
        logger.error(f"ERROR in scene_complete: {str(e)}", exc_info=True)
        return f"Error completing scene: {str(e)}"


@function_tool()
async def end_game(context: RunContext) -> str:
    """End the game early if player wants to stop"""
    
    logger.info(f"=== end_game called ===")
    
    try:
        session_id = context.agent_session.session_id
        state = get_game_state(session_id)
        
        state["phase"] = "done"
        save_session(session_id)
        
        return "early_exit_confirmed"
        
    except Exception as e:
        logger.error(f"ERROR in end_game: {str(e)}", exc_info=True)
        return f"Error ending game: {str(e)}"


@function_tool()
async def get_game_summary(context: RunContext) -> str:
    """Get summary of all rounds for closing"""
    
    logger.info(f"=== get_game_summary called ===")
    
    try:
        session_id = context.agent_session.session_id
        state = get_game_state(session_id)
        
        if not state["rounds"]:
            return "No rounds completed yet."
        
        summary = f"Game Summary for {state['player_name']}:\n\n"
        
        for i, round_data in enumerate(state["rounds"], 1):
            summary += f"Round {i}: {round_data['scenario'][:50]}...\n"
            summary += f"Style: {round_data['reaction_style']}\n\n"
        
        summary += f"Total rounds: {len(state['rounds'])}"
        
        return summary
        
    except Exception as e:
        logger.error(f"ERROR in get_game_summary: {str(e)}", exc_info=True)
        return f"Error getting summary: {str(e)}"


class ImprovBattleAgent(Agent):
    """Improv Battle Game Show Host"""
    
    def __init__(self) -> None:
        super().__init__(
            instructions="""You are the host of a TV improv show called 'Improv Battle'.

YOUR ROLE:
- High-energy, witty, and clear about rules
- React realistically to player performances (not always supportive)
- Mix praise, constructive critique, and light teasing
- Stay respectful and safe, never abusive

YOUR TOOLS:
1. start_game(player_name) - Register player and begin
2. next_scenario() - Get next improv scenario  
3. scene_complete(performance_summary) - Mark scene done, trigger reaction
4. get_game_summary() - Get all rounds for closing
5. end_game() - End early if player wants to stop

GAME FLOW:

INTRO PHASE:
- Welcome enthusiastically: "Welcome to IMPROV BATTLE! I'm your host!"
- Ask for their name
- When they give name, call start_game(player_name)
- Explain rules briefly: "You'll get 3 improv scenarios. Act them out, I'll react, then we move on!"
- Call next_scenario() to begin Round 1

SCENARIO PHASE (repeat 3 times):
- Call next_scenario() to get the scenario
- The tool returns: "Round X of 3: SCENARIO TEXT Go ahead and act it out!"
- Read the EXACT scenario text from the tool and announce it to the player
- DO NOT make up your own scenarios - ONLY use what next_scenario() returns
- Tell them to start improvising
- Listen silently while they perform - DO NOT interrupt
- When they clearly finish (say "end scene", long pause, or ask to move on):
  * Summarize what they did in 1-2 sentences
  * Call scene_complete(performance_summary)
  * The tool returns: "reaction_needed|STYLE|summary"

REACTION PHASE:
- Based on STYLE from scene_complete:
  * positive_enthusiastic: "That was HILARIOUS! The way you did that was amazing!"
  * positive_mild: "Nice work, I liked your approach there."
  * critical_constructive: "That felt a bit rushed. You could have developed it more."
  * mixed: "Interesting choice! The first part was great but the second could be stronger."
  * surprised: "Wow, I did NOT expect you to go that direction!"

- Keep reactions SHORT (2-3 sentences max)
- Be specific about what they did
- Vary your tone - not always positive!
- After reacting, if rounds remain, call next_scenario()

CLOSING PHASE (after 3 rounds):
- Call get_game_summary()
- Give a character assessment based on their overall style
- Mention 1-2 specific memorable moments
- Thank them: "Thanks for playing Improv Battle!"

EARLY EXIT:
- If they say "stop game", "end show", "I'm done":
  * Call end_game()
  * Give brief closing and thank them

CRITICAL RULES:
- Keep ALL responses SHORT (1-3 sentences) except intro and closing
- NEVER use square brackets in your speech - speak naturally
- DO NOT narrate your actions or thoughts
- React authentically - sometimes critical, sometimes amazed
- Never be mean, but honest feedback is good
- After each reaction, move forward (next scenario or closing)
- Maximum 3 rounds total

Start by greeting them enthusiastically!""",
            tools=[start_game, next_scenario, scene_complete, get_game_summary, end_game]
        )


def prewarm(proc: JobProcess):
    """Prewarm process with VAD model"""
    proc.userdata["vad"] = silero.VAD.load()


async def entrypoint(ctx: JobContext):
    """Main agent entrypoint"""
    
    logger.info("=" * 50)
    logger.info("Starting Improv Battle Agent")
    logger.info("=" * 50)
    
    # Create agent session
    session = AgentSession(
        stt=deepgram.STT(model="nova-3"),
        llm=google.LLM(
            model="gemini-2.0-flash-lite",
            temperature=0.8,
        ),
        tts=murf.TTS(
            voice="en-IN-priya", 
            style="Conversation",
            tokenizer=tokenize.basic.SentenceTokenizer(min_sentence_len=8)
        ),
        turn_detection=MultilingualModel(),
        vad=ctx.proc.userdata["vad"],
        preemptive_generation=True,
    )
    
    # Metrics
    usage_collector = metrics.UsageCollector()
    
    @session.on("user_speech_committed")
    def on_user_speech(msg):
        logger.info(f"USER SAID: {msg.text}")
    
    @session.on("agent_speech_committed")
    def on_agent_speech(msg):
        logger.info(f"AGENT SAID: {msg.text}")
    
    @session.on("function_calls_collected")
    def on_function_calls(calls):
        logger.info(f"FUNCTION CALLS: {[call.function_info.name for call in calls.function_calls]}")
    
    @session.on("metrics_collected")
    def _on_metrics_collected(ev: MetricsCollectedEvent):
        metrics.log_metrics(ev.metrics)
        usage_collector.collect(ev.metrics)
    
    async def log_usage():
        summary = usage_collector.get_summary()
        logger.info(f"Session Usage Summary: {summary}")
    
    ctx.add_shutdown_callback(log_usage)
    
    # Start agent
    await session.start(
        agent=ImprovBattleAgent(),
        room=ctx.room,
        room_input_options=RoomInputOptions(
            noise_cancellation=noise_cancellation.BVC(),
        ),
    )
    
    await ctx.connect()
    
    logger.info("Improv Battle Agent connected and ready!")


if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint, prewarm_fnc=prewarm))