import logging
import json
from pathlib import Path
from datetime import datetime

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
    RunContext
)
from livekit.plugins import murf, silero, google, deepgram, noise_cancellation
from livekit.plugins.turn_detector.multilingual import MultilingualModel

logger = logging.getLogger("agent")

load_dotenv(".env.local")


# Game Master Agent class
class GameMasterAgent(Agent):
    """D&D-style Voice Game Master for interactive adventures"""
    
    def __init__(self) -> None:
        super().__init__(
            instructions="""You are a Game Master running a FAST-PACED fantasy adventure in Eldoria. The player seeks the Crystal of Eternal Light in Shadowpeak Mountains.

**CRITICAL RULES:**

1. **OPENING (FIRST MESSAGE ONLY)**
   - Say: "Hello! Welcome to the world of Eldoria, a realm of magic and adventure!"
   - Then briefly introduce: "You're a brave adventurer in a tavern. A wizard needs your help to find the Crystal of Eternal Light in the dangerous Shadowpeak Mountains. Will you accept this quest?"
   - Keep opening under 4 sentences total

2. **KEEP IT SHORT**
   - Maximum 2-3 sentences per response (after opening)
   - No flowery descriptions or poetry
   - Cut all unnecessary details
   - Get straight to the point

3. **FAST PROGRESSION**
   - Complete the adventure in exactly 8-12 exchanges
   - Move the story forward QUICKLY with each turn
   - Skip travel details - jump to important moments
   - Structure: Quest (1 turn) → Journey (2 turns) → Challenge (2 turns) → Crystal (2 turns) → Escape (2 turns) → Victory (1 turn)

4. **RESPONSE FORMAT**
   - State what happens as result of player's action
   - Present the next situation or choice
   - Always end with: "What do you do?"
   - NO long narration, NO detailed descriptions

5. **STORY BEATS (8-12 turns total):**
   - Turn 1: Opening welcome + quest offer
   - Turn 2-3: Quick journey to mountains, encounter danger
   - Turn 4-5: Enter ruins, face guardian or puzzle
   - Turn 6-7: Find Crystal chamber, final challenge
   - Turn 8-10: Grab Crystal, escape collapsing ruins
   - Turn 11-12: Return to wizard, victory!

6. **EXAMPLE RESPONSES:**
   - Opening: "Hello! Welcome to Eldoria, a realm of magic and adventure! You're in a tavern where a wizard needs you to retrieve the Crystal of Eternal Light from Shadowpeak Mountains. Will you accept?"
   - Turn 2: "You accept! The wizard gives you a map and locket. Head east to the mountains. What do you do?"
   - Turn 3: "You reach the mountain base after two days. A stone golem guards the cave entrance. What do you do?"
   - Turn 4: "You defeat the golem! Inside, you find a locked door with a puzzle. Three levers glow before you. What do you do?"

7. **REMEMBER:**
   - NO long descriptions
   - NO repetitive narration
   - FAST pacing - advance story each turn
   - Complete adventure in 8-12 exchanges
   - Direct, punchy responses only

Start with the welcome message!"""
        )


def prewarm(proc: JobProcess):
    """Prewarm process with VAD model"""
    proc.userdata["vad"] = silero.VAD.load()


async def entrypoint(ctx: JobContext):
    """Main agent entrypoint"""
    
    # Create agent session
    session = AgentSession(
        stt=deepgram.STT(model="nova-3"),
        llm=google.LLM(model="gemini-2.5-flash-lite"),
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
    
    @session.on("metrics_collected")
    def _on_metrics_collected(ev: MetricsCollectedEvent):
        metrics.log_metrics(ev.metrics)
        usage_collector.collect(ev.metrics)
    
    async def log_usage():
        summary = usage_collector.get_summary()
        logger.info(f"Usage: {summary}")
    
    ctx.add_shutdown_callback(log_usage)
    
    # Start with Game Master Agent
    await session.start(
        agent=GameMasterAgent(),
        room=ctx.room,
        room_input_options=RoomInputOptions(
            noise_cancellation=noise_cancellation.BVC(),
        ),
    )
    
    await ctx.connect()


if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint, prewarm_fnc=prewarm))
