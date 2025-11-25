import logging
import json
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

# ------------ Content Management ------------

CONTENT_FILE = Path(__file__).parent.parent / "shared-data" / "day4_tutor_content.json"

class TutorContent:
    def __init__(self):
        self.concepts = self._load_content()
    
    def _load_content(self):
        """Load tutor content from JSON file"""
        if not CONTENT_FILE.exists():
            logger.error(f"Content file not found: {CONTENT_FILE}")
            # Create directory if it doesn't exist
            CONTENT_FILE.parent.mkdir(parents=True, exist_ok=True)
            # Create default content
            default_content = [
                {
                    "id": "variables",
                    "title": "Variables",
                    "summary": "Variables are like containers that store information in programming. You give them a name and store data in them.",
                    "sample_question": "What is a variable and why is it useful?"
                },
                {
                    "id": "loops",
                    "title": "Loops",
                    "summary": "Loops let you repeat actions multiple times. For loops run a specific number of times, while loops run until a condition is false.",
                    "sample_question": "Explain the difference between a for loop and a while loop."
                }
            ]
            with open(CONTENT_FILE, "w") as f:
                json.dump(default_content, f, indent=2)
            return default_content
        
        try:
            with open(CONTENT_FILE, "r") as f:
                return json.load(f)
        except json.JSONDecodeError as e:
            logger.error(f"Error parsing content file: {e}")
            return []
    
    def get_concept(self, concept_id: str):
        """Get a specific concept by ID"""
        for concept in self.concepts:
            if concept["id"] == concept_id:
                return concept
        return None
    
    def get_all_concepts(self):
        """Get list of all available concepts"""
        return [{"id": c["id"], "title": c["title"]} for c in self.concepts]
    
    def get_concepts_list(self):
        """Get formatted string of all concepts"""
        return ", ".join([f"{c['title']} ({c['id']})" for c in self.concepts])

# ------------ Unified Tutor Agent (Simplified version that works with current LiveKit) ------------

class UnifiedTutorAgent(Agent):
    def __init__(self, content: TutorContent):
        self.content = content
        self.current_mode = "coordinator"
        self.current_concept = None
        
        # Build dynamic instruction based on available concepts
        concepts_list = content.get_concepts_list()
        
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
    
    logger.info("🚀 Starting Teach-the-Tutor agent...")
    
    # Load tutor content
    content = TutorContent()
    logger.info(f"📚 Loaded {len(content.concepts)} concepts: {content.get_concepts_list()}")

    # Voice agent session pipeline
    session = AgentSession(
        stt=deepgram.STT(model="nova-3"),
        llm=google.LLM(model="gemini-2.5-flash"),
        tts=murf.TTS(
            voice="Iris",  # Using single reliable voice for now
            style="Conversation",
            tokenizer=tokenize.basic.SentenceTokenizer(min_sentence_len=2),
            text_pacing=True,
        ),
        turn_detection=MultilingualModel(),
        vad=ctx.proc.userdata["vad"],
        preemptive_generation=True,
    )

    # Metrics collection
    usage_collector = metrics.UsageCollector()
    
    @session.on("metrics_collected")
    def _on_metrics_collected(ev: MetricsCollectedEvent):
        metrics.log_metrics(ev.metrics)
        usage_collector.collect(ev.metrics)
    
    async def log_usage():
        summary = usage_collector.get_summary()
        logger.info(f"Usage: {summary}")
    
    ctx.add_shutdown_callback(log_usage)

    # Start session with UnifiedTutorAgent
    logger.info("🎙️ Starting agent session...")
    await session.start(
        agent=UnifiedTutorAgent(content),
        room=ctx.room,
        room_input_options=RoomInputOptions(
            noise_cancellation=noise_cancellation.BVC(),
        ),
    )

    logger.info("🔗 Connecting to room...")
    await ctx.connect()
    logger.info("✅ Agent connected successfully!")

if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint, prewarm_fnc=prewarm))
