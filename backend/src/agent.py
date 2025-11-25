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
            instructions=f"""
You are the Teach-the-Tutor AI Coach, an active recall learning assistant powered by Murf Falcon voice.

**Available concepts to learn:** {concepts_list}

**Three learning modes you can switch between:**

1. **LEARN MODE (Voice persona: Matthew - Clear Teacher)**
   - Explain concepts clearly with examples and analogies
   - Break down complex ideas into simple parts
   - Check for understanding
   - Encourage questions

2. **QUIZ MODE (Voice persona: Alicia - Engaging Quiz Master)**
   - Ask questions to test understanding
   - Listen carefully to answers
   - Provide specific, constructive feedback
   - Ask follow-up questions to deepen understanding
   - Praise what's correct, gently guide what's missing

3. **TEACH-BACK MODE (Voice persona: Ken - Supportive Coach)**
   - Ask the learner to explain the concept in their own words
   - Listen actively without interrupting
   - Provide qualitative feedback on their explanation
   - Point out what they covered well
   - Gently mention any missing key points
   - Offer suggestions for improvement

**Your Current State:**
- Mode: {self.current_mode}
- Concept: {self.current_concept['title'] if self.current_concept else 'None'}

**Instructions for each mode:**

When in COORDINATOR mode:
- Greet warmly and explain the three learning modes
- Ask which mode they want to start with
- Ask which concept they want to learn
- Use the switch_mode function to change modes

When in LEARN mode:
- Explain using the concept summary as a guide
- Add examples and real-world analogies
- Keep it conversational and engaging
- Offer to quiz them or have them teach back when done

When in QUIZ mode:
- Use the sample question to start
- Listen to their full answer
- Give specific feedback: "You got [X] right, and [Y] could be expanded..."
- Ask 2-3 follow-up questions
- Offer to review (learn mode) or teach back when done

When in TEACH-BACK mode:
- Ask them to explain the whole concept
- Listen without interrupting their full explanation
- Give feedback in this structure:
  * "Here's what you explained really well: ..."
  * "Key points you covered: ..."
  * "Here's what could be added: ..."
  * "Overall: [encouraging summary]"
- Offer to review (learn mode) or quiz when done

**Important:**
- Always be encouraging and supportive
- Adapt your teaching style to the learner's responses
- Use the switch_mode function whenever the user wants to change modes or concepts
- Keep responses conversational and avoid overly formal language
- Celebrate progress and learning milestones

**Remember:** The best way to learn is to teach! Guide them through this active recall journey.
""",
        )
    
    @function_tool
    async def switch_mode(
        self, 
        context: RunContext, 
        mode: str, 
        concept_id: str = ""
    ):
        """
        Switch to a specific learning mode with an optional concept.
        
        Args:
            mode: One of 'learn', 'quiz', or 'teach_back'
            concept_id: The concept to work on (e.g., 'variables', 'loops', 'functions', 'conditionals')
        """
        logger.info(f"Switching mode: {mode}, concept: {concept_id}")
        
        # Validate mode
        valid_modes = ["learn", "quiz", "teach_back"]
        if mode not in valid_modes:
            return f"Sorry, '{mode}' is not a valid mode. Please choose one of: {', '.join(valid_modes)}"
        
        # If concept_id provided, validate and set it
        if concept_id:
            concept = self.content.get_concept(concept_id)
            if not concept:
                available = self.content.get_concepts_list()
                return f"I don't have a concept called '{concept_id}'. Available concepts are: {available}"
            self.current_concept = concept
        
        # If no concept set yet, ask for one
        if not self.current_concept:
            available = self.content.get_concepts_list()
            return f"Which concept would you like to work on? Available concepts: {available}"
        
        # Update mode
        old_mode = self.current_mode
        self.current_mode = mode
        
        # Generate mode-specific response
        concept_title = self.current_concept['title']
        
        if mode == "learn":
            response = f"""Great! Switching to LEARN mode for {concept_title}. I'll explain it clearly.

{self.current_concept['summary']}

Let me know if you have any questions, or if you'd like to test your understanding with a quiz or teach it back to me!"""
        
        elif mode == "quiz":
            response = f"""Excellent! Switching to QUIZ mode for {concept_title}. Let's test your understanding.

Here's my question: {self.current_concept['sample_question']}

Take your time and explain your answer!"""
        
        else:  # teach_back
            response = f"""Perfect! Switching to TEACH-BACK mode for {concept_title}. 

Now it's your turn to be the teacher! Please explain {concept_title} to me in your own words. Don't worry about being perfect - just explain what you understand, and I'll give you helpful feedback.

Go ahead, teach me about {concept_title}!"""
        
        logger.info(f"Mode switched from {old_mode} to {mode} for concept {concept_title}")
        return response
    
    @function_tool
    async def list_concepts(self, context: RunContext):
        """List all available concepts to learn"""
        concepts = self.content.get_all_concepts()
        concepts_text = "\n".join([f"- {c['title']} (ID: {c['id']})" for c in concepts])
        return f"Here are all the concepts I can teach:\n{concepts_text}\n\nWhich one would you like to explore?"
    
    @function_tool
    async def get_concept_details(self, context: RunContext, concept_id: str):
        """Get detailed information about a specific concept"""
        concept = self.content.get_concept(concept_id)
        if concept:
            return f"**{concept['title']}**\n\nSummary: {concept['summary']}\n\nSample question: {concept['sample_question']}"
        return f"I couldn't find a concept with ID '{concept_id}'. Use list_concepts to see available concepts."

# ------------ Prewarm and Entrypoint ------------

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
