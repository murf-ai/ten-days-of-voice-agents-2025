import logging
from typing import Optional
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
    RunContext,
    function_tool
)
from livekit.plugins import murf, silero, google, deepgram
from livekit.plugins.turn_detector.multilingual import MultilingualModel

logger = logging.getLogger("improv-battle")
load_dotenv(".env.local")

# Improv scenarios
SCENARIOS = [
    "You are a time-travelling tour guide explaining modern smartphones to someone from the 1800s.",
    "You are a restaurant waiter who must calmly tell a customer that their order has escaped the kitchen.",
    "You are a barista who has to tell a customer that their latte is actually a portal to another dimension.",
    "You are a customer trying to return an obviously cursed object to a very skeptical shop owner.",
    "You are a librarian explaining to a patron why the book they want is currently being read by a dragon.",
]

# Agent Tools
@function_tool
async def end_scene(context: RunContext) -> str:
    """Call this when the player says they're done with their improv scene."""
    state = context.userdata
    state["waiting_for_performance"] = False
    return "Scene ended. Preparing feedback..."

@function_tool
async def next_scenario(context: RunContext) -> str:
    """Move to the next improv scenario."""
    state = context.userdata
    state["current_round"] += 1
    
    if state["current_round"] >= state["max_rounds"]:
        state["game_complete"] = True
        return "All scenarios complete! Time for final summary."
    
    scenario = SCENARIOS[state["current_round"]]
    state["waiting_for_performance"] = True
    return f"Next scenario: {scenario}"

@function_tool
async def stop_game(context: RunContext) -> str:
    """End the improv game early."""
    state = context.userdata
    state["game_complete"] = True
    return "Game stopped. Thanks for playing!"


class ImprovAgent(Agent):
    """Voice improv game show agent."""
    
    def __init__(self, llm) -> None:
        super().__init__(
            instructions=(
                "You are the host of 'Improv Battle', a fun improv game show!\n\n"
                
                "**PERSONALITY:**\n"
                "- High-energy, witty, and entertaining\n"
                "- Give REALISTIC reactions: sometimes amused, sometimes unimpressed, sometimes surprised\n"
                "- Light teasing and honest critique are allowed (but stay respectful)\n"
                "- Mix positive and critical feedback - not always supportive!\n\n"
                
                "**GAME FLOW:**\n"
                "1. **Welcome:** Greet the player warmly, ask their name\n"
                "2. **Explain:** Tell them you'll give 3 improv scenarios, they act them out, you react\n"
                "3. **Scenarios:** Present one scenario at a time from the list:\n"
                "   - Time-traveller guide with smartphones\n"
                "   - Waiter with escaped food\n"
                "   - Barista with portal latte\n"
                "   - Returning cursed object\n"
                "   - Librarian with dragon reader\n"
                "4. **Listen:** Let them perform! Don't interrupt\n"
                "5. **React:** After they finish (or call end_scene), give honest feedback:\n"
                "   - 'That was hilarious when you...'\n"
                "   - 'That felt rushed, you could have...'\n"
                "   - 'Interesting choice to...'\n"
                "6. **Continue:** Use next_scenario to move forward\n"
                "7. **Close:** After 3 rounds, give a fun summary of their improv style\n\n"
                
                "**TOOLS:**\n"
                "- end_scene: Use when player says 'end scene', 'done', 'that's it'\n"
                "- next_scenario: After giving feedback, move to next round\n"
                "- stop_game: If player wants to quit early\n\n"
                
                "**IMPORTANT:**\n"
                "- Keep reactions brief (2-3 sentences)\n"
                "- Be specific about what they did\n"
                "- Vary your tone: supportive, critical, surprised, amused\n"
                "- Make it feel like a real TV show!\n"
            ),
            tools=[end_scene, next_scenario, stop_game],
            llm=llm
        )

# Entrypoint
async def entrypoint(ctx: JobContext):
    """Main entrypoint."""
    
    # Initialize game state
    game_state = {
        "player_name": None,
        "current_round": 0,
        "max_rounds": 3,
        "waiting_for_performance": False,
        "game_complete": False
    }
    
    ctx.log_context_fields = {"room": ctx.room.name}
    llm = google.LLM(model="gemini-2.5-flash")
    
    session = AgentSession(
        stt=deepgram.STT(model="nova-3"),
        llm=llm,
        tts=murf.TTS(
            voice="en-US-alicia",
            style="Conversation",
            tokenizer=tokenize.basic.SentenceTokenizer(min_sentence_len=2),
            text_pacing=True
        ),
        turn_detection=MultilingualModel(),
        vad=silero.VAD.load(),
        preemptive_generation=True,
    )
    
    session.userdata = game_state
    
    # Metrics
    usage_collector = metrics.UsageCollector()
    
    @session.on("metrics_collected")
    def _on_metrics_collected(ev: MetricsCollectedEvent):
        metrics.log_metrics(ev.metrics)
        usage_collector.collect(ev.metrics)
    
    async def log_usage():
        summary = usage_collector.get_summary()
        logger.info(f"Usage: {summary}")
    
    ctx.add_shutdown_callback(log_usage)
    
    # Start session
    await session.start(agent=ImprovAgent(llm=llm), room=ctx.room)
    await ctx.connect()

def prewarm(proc: JobProcess):
    """Preload resources."""
    pass

if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint, prewarm_fnc=prewarm))
