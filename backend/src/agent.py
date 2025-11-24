import logging
import json
from datetime import datetime
from pathlib import Path

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
load_dotenv(".env.local")

# ------------ Wellness Data Management ------------

WELLNESS_LOG_FILE = "wellness_log.json"

class WellnessLogger:
    def __init__(self):
        self.log_file = Path(WELLNESS_LOG_FILE)
        self.entries = self._load_entries()

    def _load_entries(self):
        """Load existing wellness log entries from JSON file"""
        if self.log_file.exists():
            try:
                with open(self.log_file, "r") as f:
                    return json.load(f)
            except json.JSONDecodeError:
                logger.warning(f"Could not parse {WELLNESS_LOG_FILE}, starting fresh")
                return []
        return []

    def get_last_entry(self):
        """Get the most recent wellness check-in"""
        if self.entries:
            return self.entries[-1]
        return None

    def add_entry(self, mood: str, energy: str, objectives: list, stress: str = ""):
        """Add a new wellness check-in entry"""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "date": datetime.now().strftime("%Y-%m-%d"),
            "time": datetime.now().strftime("%H:%M"),
            "mood": mood,
            "energy": energy,
            "stress": stress,
            "objectives": objectives,
            "summary": f"User reported feeling {mood} with {energy} energy. Goals: {', '.join(objectives)}"
        }
        
        self.entries.append(entry)
        
        # Save to file
        with open(self.log_file, "w") as f:
            json.dump(self.entries, f, indent=2)
        
        logger.info(f"Saved wellness entry: {entry}")
        return entry

    def get_context_summary(self):
        """Get a summary of recent entries for agent context"""
        if not self.entries:
            return "This is the user's first check-in."
        
        last_entry = self.entries[-1]
        return f"Last check-in on {last_entry['date']}: User felt {last_entry['mood']} with {last_entry['energy']} energy. Their goals were: {', '.join(last_entry['objectives'])}."

# ------------ Wellness Check-in State ------------

class CheckInState:
    def __init__(self):
        self.state = {
            "mood": "",
            "energy": "",
            "stress": "",
            "objectives": []
        }

    def is_complete(self):
        """Check if all required fields are filled"""
        return all([
            self.state["mood"],
            self.state["energy"],
            len(self.state["objectives"]) > 0
        ])

    def missing_fields(self):
        """Return list of fields that still need to be collected"""
        missing = []
        if not self.state["mood"]:
            missing.append("mood")
        if not self.state["energy"]:
            missing.append("energy level")
        if len(self.state["objectives"]) == 0:
            missing.append("today's objectives")
        return missing

# ------------ Health & Wellness Agent ------------

class HealthWellnessAgent(Agent):
    def __init__(self):
        # Load previous check-ins
        self.wellness_logger = WellnessLogger()
        context_summary = self.wellness_logger.get_context_summary()
        
        super().__init__(
            instructions="""You are a helpful voice AI assistant. The user is interacting with you via voice, even if you perceive the conversation as text.
            You eagerly assist users with their questions by providing information from your extensive knowledge.
            Your responses are concise, to the point, and without any complex formatting including emojis, asterisks, or other weird symbols.
            You are curious, friendly, and have a sense of humor.""",
        )

    # To add tools, use the @function_tool decorator.
    # Here's an example that adds a simple weather tool.
    # You also have to add `from livekit.agents import function_tool, RunContext` to the top of this file
    # @function_tool
    # async def lookup_weather(self, context: RunContext, location: str):
    #     """Use this tool to look up current weather information in the given location.
    #
    #     If the location is not supported by the weather service, the tool will indicate this. You must tell the user the location's weather is unavailable.
    #
    #     Args:
    #         location: The location to look up weather information for (e.g. city name)
    #     """
    #
    #     logger.info(f"Looking up weather for {location}")
    #
    #     return "sunny with a temperature of 70 degrees."


def prewarm(proc: JobProcess):
    proc.userdata["vad"] = silero.VAD.load()

async def entrypoint(ctx: JobContext):
    # Logging setup
    ctx.log_context_fields = {
        "room": ctx.room.name,
    }

    # Voice agent session pipeline
    session = AgentSession(
        stt=deepgram.STT(model="nova-3"),
        llm=google.LLM(model="gemini-2.5-flash"),
        tts=murf.TTS(
            voice="Iris",  # Warm, friendly voice
            style="Conversation",
            tokenizer=tokenize.basic.SentenceTokenizer(min_sentence_len=2),
            text_pacing=True,
        ),
        turn_detection=MultilingualModel(),
        vad=ctx.proc.userdata["vad"],
        preemptive_generation=True,
    )

    # Metrics collection (optional)
    usage_collector = metrics.UsageCollector()
    
    @session.on("metrics_collected")
    def _on_metrics_collected(ev: MetricsCollectedEvent):
        metrics.log_metrics(ev.metrics)
        usage_collector.collect(ev.metrics)
    
    async def log_usage():
        summary = usage_collector.get_summary()
        logger.info(f"Usage: {summary}")
    
    ctx.add_shutdown_callback(log_usage)

    # Start session using HealthWellnessAgent
    await session.start(
        agent=HealthWellnessAgent(),
        room=ctx.room,
        room_input_options=RoomInputOptions(
            noise_cancellation=noise_cancellation.BVC(),
        ),
    )

    await ctx.connect()

if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint, prewarm_fnc=prewarm))
