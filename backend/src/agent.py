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
    RunContext
)
from livekit.plugins import murf, silero, google, deepgram, noise_cancellation
from livekit.plugins.turn_detector.multilingual import MultilingualModel

logger = logging.getLogger("agent")

load_dotenv(".env.local")

# Load tutor content
def load_tutor_content():
    """Load concepts from the JSON file"""
    content_file = Path("shared-data/day4_tutor_content.json")
    try:
        with open(content_file, "r") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error loading tutor content: {e}")
        return []

CONCEPTS = load_tutor_content()

# Session state
session_state = {
    "current_concept_id": None
}



class GreeterAgent(Agent):
    """Initial agent that greets and routes to learning mode agents"""
    
    def __init__(self) -> None:
        concept_list = "\n".join([f"- {c['title']}" for c in CONCEPTS])
        
        super().__init__(
            instructions=f"""You are a friendly Active Recall Coach greeter. Your job is to:

1. Greet warmly: "Hi! I'm your Active Recall Coach. I help you learn programming concepts effectively through active recall."

2. Explain the THREE learning modes:
   - LEARN mode: I'll explain concepts to you clearly
   - QUIZ mode: I'll ask you questions to test your knowledge
   - TEACH_BACK mode: You teach concepts back to me and I give feedback

3. Ask which mode they'd like to start with

4. Once they choose, use the appropriate handoff tool to connect them to that mode's agent

Available concepts: {concept_list}

Keep it brief and friendly. Once they choose a mode, immediately use the handoff tool!
""",
        )
    
    @function_tool
    async def handoff_to_learn(self, context: RunContext):
        """Transfer to Learn mode with Matthew voice"""
        logger.info("Handing off to Learn mode (Matthew)")
        return LearnAgent(chat_ctx=self.chat_ctx)
    
    @function_tool
    async def handoff_to_quiz(self, context: RunContext):
        """Transfer to Quiz mode with Alicia voice"""
        logger.info("Handing off to Quiz mode (Alicia)")
        return QuizAgent(chat_ctx=self.chat_ctx)
    
    @function_tool
    async def handoff_to_teach_back(self, context: RunContext):
        """Transfer to Teach Back mode with Ken voice"""
        logger.info("Handing off to Teach Back mode (Ken)")
        return TeachBackAgent(chat_ctx=self.chat_ctx)


class LearnAgent(Agent):
    """Learn mode agent - explains concepts (Matthew voice)"""
    
    def __init__(self, chat_ctx=None) -> None:
        concept_list = "\n".join([f"- {c['title']} ({c['id']})" for c in CONCEPTS])
        
        super().__init__(
            instructions=f"""You are in LEARN mode. You're a patient teacher who explains programming concepts clearly.

Available concepts:
{concept_list}

Your process:
1. Ask which concept they'd like to learn about
2. Use explain_concept tool to get the explanation
3. Read the explanation from the tool EXACTLY as provided - do NOT add extra information beyond what the tool returns
4. After explaining, ask if they want to learn another concept or switch modes
5. If switching modes, use the appropriate handoff tool

IMPORTANT: Only explain what is provided in the tool's response. Do not elaborate or add your own explanations.

Be friendly and clear. You're Matthew, the teacher!
""",
            chat_ctx=chat_ctx,
            tts=murf.TTS(
                voice="en-US-matthew", 
                style="Conversation",
                tokenizer=tokenize.basic.SentenceTokenizer(min_sentence_len=8)
            )
        )
    
    async def on_enter(self) -> None:
        """Called when entering Learn mode"""
        await self.session.generate_reply(
            instructions="Welcome to Learn mode! I'm Matthew, your teacher. Which concept would you like to learn about?"
        )
    
    @function_tool
    async def explain_concept(self, context: RunContext, concept_id: str):
        """Get the explanation for a concept (LEARN mode)
        
        Args:
            concept_id: The ID of the concept to explain (e.g., 'variables', 'loops', 'functions')
        """
        global session_state
        concept = next((c for c in CONCEPTS if c["id"] == concept_id), None)
        if concept:
            session_state["current_concept_id"] = concept_id
            session_state["current_mode"] = "learn"
            return f"Concept: {concept['title']}\n\nExplanation: {concept['summary']}"
        return "I don't have information about that concept. Available concepts are: " + ", ".join([c['id'] for c in CONCEPTS])
    
    @function_tool
    async def handoff_to_quiz(self, context: RunContext):
        """Switch to Quiz mode"""
        logger.info("Handing off from Learn to Quiz mode")
        return QuizAgent(chat_ctx=self.chat_ctx)
    
    @function_tool
    async def handoff_to_teach_back(self, context: RunContext):
        """Switch to Teach Back mode"""
        logger.info("Handing off from Learn to Teach Back mode")
        return TeachBackAgent(chat_ctx=self.chat_ctx)


class QuizAgent(Agent):
    """Quiz mode agent - asks questions (Alicia voice)"""
    
    def __init__(self, chat_ctx=None) -> None:
        concept_list = "\n".join([f"- {c['title']} ({c['id']})" for c in CONCEPTS])
        
        super().__init__(
            instructions=f"""You are in QUIZ mode. You're an engaging quiz master who tests knowledge with encouragement.

Available concepts:
{concept_list}

Your process:
1. Ask which concept they'd like to be quizzed on
2. Use get_quiz_question tool to get a question
3. Ask the question and listen to their answer
4. Give encouraging, constructive feedback on their answer
5. Ask if they want another question or to switch modes
6. If switching modes, use the appropriate handoff tool

Be positive and encouraging. You're Alicia, the quiz master!
""",
            chat_ctx=chat_ctx,
            tts=murf.TTS(
                voice="en-US-alicia", 
                style="Conversation",
                tokenizer=tokenize.basic.SentenceTokenizer(min_sentence_len=8)
            )
        )
    
    async def on_enter(self) -> None:
        """Called when entering Quiz mode"""
        await self.session.generate_reply(
            instructions="Welcome to Quiz mode! I'm Alicia, your quiz master. Which concept would you like to be quizzed on?"
        )
    
    @function_tool
    async def get_quiz_question(self, context: RunContext, concept_id: str):
        """Get a quiz question for a concept
        
        Args:
            concept_id: The ID of the concept to quiz on (e.g., 'variables', 'loops')
        """
        global session_state
        concept = next((c for c in CONCEPTS if c["id"] == concept_id), None)
        if concept:
            session_state["current_concept_id"] = concept_id
            return f"Quiz question for {concept['title']}: {concept['sample_question']}"
        return "I don't have a quiz for that concept. Available concepts are: " + ", ".join([c['id'] for c in CONCEPTS])
    
    @function_tool
    async def handoff_to_learn(self, context: RunContext):
        """Switch to Learn mode"""
        logger.info("Handing off from Quiz to Learn mode")
        return LearnAgent(chat_ctx=self.chat_ctx)
    
    @function_tool
    async def handoff_to_teach_back(self, context: RunContext):
        """Switch to Teach Back mode"""
        logger.info("Handing off from Quiz to Teach Back mode")
        return TeachBackAgent(chat_ctx=self.chat_ctx)


class TeachBackAgent(Agent):
    """Teach Back mode agent - user teaches, agent evaluates (Ken voice)"""
    
    def __init__(self, chat_ctx=None) -> None:
        concept_list = "\n".join([f"- {c['title']} ({c['id']})" for c in CONCEPTS])
        
        super().__init__(
            instructions=f"""You are in TEACH_BACK mode. You're a supportive coach who learns from the user.

Available concepts:
{concept_list}

Your process:
1. Ask which concept they'd like to teach you
2. Use get_teach_back_prompt tool to prompt them
3. Listen carefully to their explanation
4. Use evaluate_explanation tool to assess it
5. Give encouraging feedback based on the evaluation
6. Ask if they want to teach another concept or switch modes
7. If switching modes, use the appropriate handoff tool

Be supportive and encouraging. You're Ken, the learning coach!
Remember: Teaching is the best way to learn!
""",
            chat_ctx=chat_ctx,
            tts=murf.TTS(
                voice="en-US-ken", 
                style="Conversation",
                tokenizer=tokenize.basic.SentenceTokenizer(min_sentence_len=8)
            )
        )
    
    async def on_enter(self) -> None:
        """Called when entering Teach Back mode"""
        await self.session.generate_reply(
            instructions="Welcome to Teach Back mode! I'm Ken, your learning coach. Which concept would you like to teach me about?"
        )
    
    @function_tool
    async def get_teach_back_prompt(self, context: RunContext, concept_id: str):
        """Get the prompt for teaching back a concept
        
        Args:
            concept_id: The ID of the concept they'll teach (e.g., 'variables', 'loops')
        """
        global session_state
        concept = next((c for c in CONCEPTS if c["id"] == concept_id), None)
        if concept:
            session_state["current_concept_id"] = concept_id
            return f"Great! Please teach me about {concept['title']}. Explain it as if I'm a complete beginner. I'm listening!"
        return "I don't have that concept. Available concepts are: " + ", ".join([c['id'] for c in CONCEPTS])
    
    @function_tool
    async def evaluate_explanation(
        self, 
        context: RunContext, 
        concept_id: str,
        user_explanation: str
    ):
        """Evaluate the user's explanation and provide feedback
        
        Args:
            concept_id: The concept they explained
            user_explanation: What the user said
        """
        concept = next((c for c in CONCEPTS if c["id"] == concept_id), None)
        if not concept:
            return "I couldn't find that concept to evaluate."
        
        # Simple keyword-based evaluation
        explanation = user_explanation.lower()
        
        key_terms = {
            "variables": ["store", "value", "name", "reuse"],
            "loops": ["repeat", "for", "while", "multiple"],
            "functions": ["reusable", "block", "code", "task", "call"],
            "conditionals": ["if", "condition", "decision", "true", "false"],
            "data_types": ["integer", "string", "float", "boolean", "type"]
        }
        
        terms = key_terms.get(concept_id, [])
        matches = sum(1 for term in terms if term in explanation)
        coverage = matches / len(terms) if terms else 0.5
        
        # Generate qualitative feedback
        if coverage >= 0.75:
            assessment = "Excellent"
            feedback = "You covered the key concepts really well! Your explanation was clear and comprehensive."
        elif coverage >= 0.5:
            assessment = "Good"
            feedback = "You got the main ideas! You could strengthen your explanation by mentioning a few more details."
        else:
            assessment = "Needs improvement"
            feedback = "You're on the right track, but try to include more of the core concepts. Would you like to switch to Learn mode first?"
        
        return f"Assessment: {assessment}\n\nFeedback: {feedback}\n\nKeep teaching - you're learning by doing!"
    
    @function_tool
    async def handoff_to_learn(self, context: RunContext):
        """Switch to Learn mode"""
        logger.info("Handing off from Teach Back to Learn mode")
        return LearnAgent(chat_ctx=self.chat_ctx)
    
    @function_tool
    async def handoff_to_quiz(self, context: RunContext):
        """Switch to Quiz mode"""
        logger.info("Handing off from Teach Back to Quiz mode")
        return QuizAgent(chat_ctx=self.chat_ctx)




def prewarm(proc: JobProcess):
    proc.userdata["vad"] = silero.VAD.load()


async def entrypoint(ctx: JobContext):
    # Logging setup
    ctx.log_context_fields = {
        "room": ctx.room.name,
    }
    
    # Create main session - each agent will configure its own TTS
    session = AgentSession(
        stt=deepgram.STT(model="nova-3"),
        llm=google.LLM(model="gemini-2.5-flash-lite"),
        tts=murf.TTS(
            voice="en-US-matthew", 
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
    
    # Start with greeter agent
    await session.start(
        agent=GreeterAgent(),
        room=ctx.room,
        room_input_options=RoomInputOptions(
            noise_cancellation=noise_cancellation.BVC(),
        ),
    )
    
    await ctx.connect()




if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint, prewarm_fnc=prewarm))
    

