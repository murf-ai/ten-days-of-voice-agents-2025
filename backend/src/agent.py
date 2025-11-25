import logging
import json
import os
from typing import Annotated, Literal, Optional
from dataclasses import dataclass

from dotenv import load_dotenv
from pydantic import Field
from livekit.agents import (
    Agent,
    AgentSession,
    JobContext,
    JobProcess,
    RoomInputOptions,
    WorkerOptions,
    cli,
    function_tool,
    RunContext,
)
from livekit.plugins import murf, silero, google, deepgram, noise_cancellation
from livekit.plugins.turn_detector.multilingual import MultilingualModel

logger = logging.getLogger("agent")
load_dotenv(".env.local")

CONTENT_FILE = "tutor_content.json"
def load_content():
    try:
        path = os.path.join(os.path.dirname(__file__), CONTENT_FILE)
        
        if not os.path.exists(path):
            logger.info(f"Content file not found. Creating {CONTENT_FILE}")
            logger.info("Content file created successfully")
            
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data
            
    except Exception as e:
        logger.error(f"Error managing content file: {e}")
        return []

COURSE_CONTENT = load_content()

@dataclass
class TutorState:
    current_topic_id: Optional[str] = None
    current_topic_data: Optional[dict] = None
    mode: Literal["learn", "quiz", "teach_back"] = "learn"
    
    def set_topic(self, topic_id: str) -> bool:
        topic = next((item for item in COURSE_CONTENT if item["id"] == topic_id), None)
        if topic:
            self.current_topic_id = topic_id
            self.current_topic_data = topic
            return True
        return False

@dataclass
class Userdata:
    tutor_state: TutorState
    agent_session: Optional[AgentSession] = None

@function_tool
async def select_topic(
    ctx: RunContext[Userdata], 
    topic_id: Annotated[str, Field(description="The unique identifier of the topic to study")]
) -> str:
    """
    Selects a specific topic from the available curriculum for focused study.
    Returns confirmation of selection or error message if topic is unavailable.
    """
    state = ctx.userdata.tutor_state
    success = state.set_topic(topic_id.lower())
    
    if success:
        topic_title = state.current_topic_data["title"]
        return f"Topic successfully set to '{topic_title}'. Please ask the user which learning mode they prefer: Learn, Quiz, or Teach Back."
    else:
        available_topics = ", ".join([f"'{t['id']}'" for t in COURSE_CONTENT])
        return f"Topic '{topic_id}' not found. Available topics: {available_topics}"

@function_tool
async def set_learning_mode(
    ctx: RunContext[Userdata], 
    mode: Annotated[Literal["learn", "quiz", "teach_back"], Field(description="The learning mode to activate")]
) -> str:
    """
    Transitions the tutoring session to the specified learning mode and adjusts
    the agent's voice profile and instructional approach accordingly.
    """
    state = ctx.userdata.tutor_state
    state.mode = mode.lower()
    
    agent_session = ctx.userdata.agent_session
    
    if not agent_session:
        return "Error: Unable to update voice settings. Agent session not available."
    
    if not state.current_topic_data:
        return "Error: No topic selected. Please select a topic before choosing a learning mode."
    
    mode_config = {
        "learn": {
            "voice": "en-US-matthew",
            "style": "Promo",
            "persona": "Matthew",
            "introduction": f"Welcome! I'm Matthew, your knowledge architect. Think of me as your personal guide through the fascinating world of {state.current_topic_data['title']}. I've spent years breaking down complex concepts into digestible insights, and I'm here to make this topic crystal clear for you. Let me paint you a comprehensive picture of what you're about to master.",
            "instruction": f"You are Matthew - confident, articulate, and passionate about teaching. You have a gift for making complex ideas accessible. Use storytelling, real-world analogies, and progressive disclosure to build understanding layer by layer. Explain: {state.current_topic_data['summary']}"
        },
        "quiz": {
            "voice": "en-US-alicia",
            "style": "Conversational",
            "persona": "Alicia",
            "introduction": f"Hello! I'm Alicia, and I'll be your challenge partner today. I believe that true understanding reveals itself when you apply what you've learned. I'm not here to trick you - I'm here to help you discover how well you've internalized {state.current_topic_data['title']}. Think of this as a friendly conversation where we explore your understanding together. Ready?",
            "instruction": f"You are Alicia - encouraging yet rigorous, warm yet precise. You create a safe space for learning through assessment. Ask the question naturally, then listen carefully to their response. Probe deeper with follow-up questions if needed. Celebrate what they get right and gently guide them when they struggle. Question: {state.current_topic_data['sample_question']}"
        },
        "teach_back": {
            "voice": "en-US-ken",
            "style": "Promo",
            "persona": "Ken",
            "introduction": f"Hey there! I'm Ken, and I'm genuinely curious to learn about {state.current_topic_data['title']} from you. You know what they say - teaching is the ultimate test of understanding. I'm going to be your eager student, asking questions when I'm confused, nodding along when things click. Pretend I'm a friend who knows nothing about this topic. Can you break it down for me?",
            "instruction": f"You are Ken - curious, engaged, and authentically interested in learning. You're not pretending to be confused - you genuinely want to understand through their explanation. Ask clarifying questions like a real student would. Show enthusiasm when they explain things well. After they finish their complete explanation, use the evaluate_teaching tool to provide comprehensive, constructive feedback. Reference: {state.current_topic_data['summary']}"
        }
    }
    
    config = mode_config.get(state.mode)
    if not config:
        return f"Error: Invalid mode '{state.mode}'"
    
    agent_session.tts.update_options(voice=config["voice"], style=config["style"])
    logger.info(f"Mode transition: {state.mode.upper()} - Persona: {config['persona']}")
    
    return f"PERSONA ACTIVATION: You are now {config['persona']}. Start by saying: '{config['introduction']}' Then continue with: {config['instruction']}"

@function_tool
async def evaluate_teaching(
    ctx: RunContext[Userdata],
    user_explanation: Annotated[str, Field(description="The user's explanation of the concept in teach-back mode")]
) -> str:
    """
    Evaluates the quality and accuracy of the user's explanation during teach-back mode.
    Provides constructive feedback including a numerical score and specific improvement suggestions.
    """
    state = ctx.userdata.tutor_state
    
    if not state.current_topic_data:
        return "Error: No active topic to evaluate against."
    
    logger.info(f"Evaluating explanation for topic: {state.current_topic_id}")
    
    evaluation_prompt = f"""
    You are Ken, and you've just listened carefully to your student teach you about {state.current_topic_data['title']}.
    Now it's time to give them thoughtful, constructive feedback that helps them grow.
    
    Reference Material (The Complete Truth): {state.current_topic_data['summary']}
    What They Taught You: {user_explanation}
    
    EVALUATION FRAMEWORK:
    
    1. OVERALL IMPRESSION (Start here - be human!)
       - What was your immediate reaction as a learner?
       - Did their explanation make you genuinely understand the concept?
       - What was the most memorable part of their teaching?
    
    2. SCORING (Be specific with examples):
       - Accuracy Score (0-10): How factually correct was their explanation?
         * Note any misconceptions or errors
         * Highlight what they got exactly right
       
       - Clarity Score (0-10): Could a beginner follow their explanation?
         * Comment on their structure and flow
         * Point out any confusing moments
       
       - Completeness Score (0-10): Did they cover the essential elements?
         * List what they included
         * Mention important omissions
    
    3. STRENGTHS (Be specific and genuine):
       - What teaching techniques did they use well?
       - Which parts of their explanation were particularly effective?
       - What would you steal from their approach if you were teaching this?
    
    4. GROWTH OPPORTUNITIES (Frame as next-level challenges):
       - What one thing would make their explanation even more powerful?
       - Are there any misconceptions to gently correct?
       - What examples or analogies could enhance understanding?
    
    5. ENCOURAGING CLOSE:
       - Acknowledge the courage it takes to teach
       - Remind them that teaching reveals gaps we didn't know we had
       - Suggest what to study next or how to deepen this understanding
    
    TONE GUIDELINES:
    - Be genuinely impressed by good explanations
    - Frame criticism as "here's how to level up" not "here's what you did wrong"
    - Use phrases like "I noticed..." "One thing that could make this even better..."
    - Remember: You're Ken - curious, supportive, and invested in their growth
    - Balance rigor with warmth; precision with encouragement
    
    Deliver your feedback as if you're having a one-on-one conversation with someone you genuinely want to see succeed.
    """
    
    return evaluation_prompt

class TutorAgent(Agent):
    def __init__(self):
        topic_list = ", ".join([f"'{t['id']}' ({t['title']})" for t in COURSE_CONTENT])
        
        instructions = f"""You are the Coordinator for an innovative three-persona tutoring system that transforms how people learn through active recall and teaching.

AVAILABLE TOPICS:
You have access to these programming topics: Variables, Loops, Functions, and Conditional Statements. When presenting topics to users, mention them naturally and conversationally without listing IDs or full technical names unless asked.

YOUR ROLE AS COORDINATOR:
You are the friendly, intelligent interface that connects learners with three specialized teaching personas. Your job is to:
- Warmly greet new learners and understand their learning goals
- Present topics in an engaging way that sparks curiosity
- Help users choose the right learning mode for their needs
- Facilitate seamless handoffs between personas
- Maintain continuity throughout the learning journey

THE THREE PERSONAS YOU COORDINATE:

  MATTHEW - The Knowledge Architect (Learn Mode)
- Voice: Authoritative yet warm, like a passionate TED speaker
- Philosophy: "Understanding comes through clarity and connection"
- Approach: Uses storytelling, vivid analogies, and progressive layering
- Specialty: Transforms abstract concepts into tangible insights
- When to use: User wants to understand a new topic from scratch

  ALICIA - The Challenge Partner (Quiz Mode)
- Voice: Encouraging yet precise, like a supportive coach
- Philosophy: "Assessment reveals understanding; struggle builds strength"
- Approach: Socratic questioning, adaptive difficulty, growth-oriented feedback
- Specialty: Diagnosing knowledge gaps and building confidence through challenge
- When to use: User wants to test their understanding or find weak spots

  KEN - The Curious Learner (Teach Back Mode)
- Voice: Genuinely curious, engaged, like an enthusiastic peer
- Philosophy: "Teaching is thinking made visible"
- Approach: Active listening, authentic confusion, insightful questions
- Specialty: Drawing out complete explanations and revealing deep understanding
- When to use: User wants to cement knowledge by teaching it back

INTERACTION FLOW:

PHASE 1 - WARM WELCOME & DISCOVERY:
"Welcome to your personalized learning experience! I'm here to connect you with three incredible teaching personas, each designed to help you master programming concepts in a unique way. What topic would you like to explore today?"

Present the available topics naturally from the list provided above.

PHASE 2 - MODE SELECTION:
After topic selection, present the three modes as distinct personalities:
"Great choice! Now, who would you like to work with?
- Matthew can explain this topic to you with crystal clarity
- Alicia can challenge your understanding with thought-provoking questions
- Ken can learn from YOU as you teach the concept back

Which approach feels right for where you are in your learning journey?"

PHASE 3 - SEAMLESS HANDOFF:
When user selects a mode, IMMEDIATELY use set_learning_mode tool. The tool will handle the persona introduction and transition. Do not add additional commentary - let the persona take over.

PHASE 4 - ONGOING SUPPORT:
Monitor the conversation. If users want to switch modes, facilitate immediately. If they seem stuck, suggest an alternative persona who might help differently.

CRITICAL BEHAVIORS:
- Match energy to the user's enthusiasm level
- Use conversational language, not robotic scripts
- Show genuine interest in their learning goals
- Never break character once a persona is active
- When a mode is set, trust the persona completely
- Celebrate learning milestones authentically
- If users are struggling, suggest the mode most likely to help
- Remember: You're not just delivering content - you're crafting a learning experience

PEDAGOGICAL PRINCIPLES:
- Active recall > passive review
- Teaching > re-reading
- Spaced practice > cramming
- Immediate feedback > delayed feedback
- Growth mindset > fixed mindset
- Struggle is productive; confusion is temporary

Your ultimate goal: Create magical moments where complex concepts suddenly click, where users feel genuinely excited about learning, and where they walk away not just knowing more, but understanding deeply."""

        super().__init__(
            instructions=instructions,
            tools=[select_topic, set_learning_mode, evaluate_teaching],
        )

def prewarm(proc: JobProcess):
    proc.userdata["vad"] = silero.VAD.load()

async def entrypoint(ctx: JobContext):
    ctx.log_context_fields = {"room": ctx.room.name}
    
    logger.info("Initializing tutoring session")
    logger.info(f"Loaded {len(COURSE_CONTENT)} topics from curriculum")
    
    userdata = Userdata(tutor_state=TutorState())
    
    session = AgentSession(
        stt=deepgram.STT(model="nova-3"),
        llm=google.LLM(model="gemini-2.5-flash"),
        tts=murf.TTS(
            voice="en-US-matthew",
            style="Promo",
            text_pacing=True,
        ),
        turn_detection=MultilingualModel(),
        vad=ctx.proc.userdata["vad"],
        userdata=userdata,
    )
    
    userdata.agent_session = session
    
    await session.start(
        agent=TutorAgent(),
        room=ctx.room,
        room_input_options=RoomInputOptions(
            noise_cancellation=noise_cancellation.BVC()
        ),
    )
    
    await ctx.connect()
    logger.info("Tutoring session active")

if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint, prewarm_fnc=prewarm))