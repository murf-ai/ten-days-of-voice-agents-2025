import logging
import json
import os
import re
from dataclasses import dataclass, asdict, field
from typing import Optional, List, Dict, Any
from datetime import datetime

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
    function_tool,
    RunContext
)
from livekit.plugins import murf, silero, google, deepgram
from livekit.plugins.turn_detector.multilingual import MultilingualModel

logger = logging.getLogger("agent")
load_dotenv(".env.local")

# --- Load FAQ Content ---
FAQ_FILE = "shared-data/faq_razorpay.json"

def load_faq_content():
    """Load FAQ content from JSON file."""
    try:
        with open(FAQ_FILE, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        logger.error(f"FAQ file not found: {FAQ_FILE}")
        return {"company": "Company", "faqs": [], "lead_fields": {}}

FAQ_DATA = load_faq_content()
COMPANY_NAME = FAQ_DATA.get("company", "Company")

# --- Lead Capture State ---
@dataclass
class LeadData:
    """Stores lead information."""
    name: Optional[str] = None
    email: Optional[str] = None
    company: Optional[str] = None
    monthly_volume: Optional[str] = None
    use_case: Optional[str] = None
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def is_complete(self) -> bool:
        """Check if all required fields are filled."""
        return all([self.name, self.email, self.company, self.monthly_volume, self.use_case])
    
    def to_json_file(self) -> str:
        """Save lead to JSON file."""
        filename = f"lead_{self.name.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(filename, 'w') as f:
            json.dump(asdict(self), f, indent=4)
        logger.info(f"Lead saved to {filename}")
        return filename

# --- Simple FAQ Matching ---
def find_best_faq(user_query: str) -> Optional[Dict[str, Any]]:
    """Find the best matching FAQ using keyword matching."""
    user_query_lower = user_query.lower()
    
    best_match = None
    best_score = 0
    
    for faq in FAQ_DATA.get("faqs", []):
        score = 0
        keywords = faq.get("keywords", [])
        
        for keyword in keywords:
            if keyword.lower() in user_query_lower:
                score += len(keyword.split())  # Longer phrases get higher scores
        
        if score > best_score:
            best_score = score
            best_match = faq
    
    # Return match if score is high enough
    if best_score >= 1:  # At least one keyword matched
        return best_match
    
    return None

# --- Tools ---
@function_tool
async def search_faq(
    context: RunContext,
    user_question: str
) -> str:
    """
    Search the FAQ database for relevant information.
    
    Args:
        user_question: The user's question about the company or services
    """
    logger.info(f"Searching FAQ for: {user_question}")
    
    faq = find_best_faq(user_question)
    
    if faq:
        return f"FAQ_FOUND: {faq['answer']}"
    else:
        return f"FAQ_NOT_FOUND: {FAQ_DATA.get('no_match_response', 'I need to connect you with our sales team.')}"

@function_tool
async def capture_lead(
    context: RunContext,
    name: Optional[str] = None,
    email: Optional[str] = None,
    company: Optional[str] = None,
    monthly_volume: Optional[str] = None,
    use_case: Optional[str] = None
) -> str:
    """
    Capture lead information from the user.
    
    Args:
        name: User's full name
        email: User's email address
        company: User's company name
        monthly_volume: Expected monthly transaction volume
        use_case: Primary use case (e.g., e-commerce, subscriptions)
    """
    lead: LeadData = context.userdata.get("lead", LeadData())
    
    # Update fields
    if name: lead.name = name
    if email: lead.email = email
    if company: lead.company = company
    if monthly_volume: lead.monthly_volume = monthly_volume
    if use_case: lead.use_case = use_case
    
    # Save back to context
    context.userdata["lead"] = lead
    
    # Check if complete
    if lead.is_complete():
        filename = lead.to_json_file()
        
        # Send to frontend
        try:
            await context.room.local_participant.publish_data(
                json.dumps({
                    "type": "LEAD_CAPTURED",
                    "lead": asdict(lead)
                }).encode('utf-8'),
                topic="lead_capture"
            )
            logger.info("Lead data sent to frontend")
        except Exception as e:
            logger.error(f"Failed to send lead data: {e}")
        
        return (
            f"LEAD_COMPLETE: Thank you {lead.name}! I've captured all your information. "
            f"Our sales team will reach out to you at {lead.email} within 24 hours to discuss "
            f"how {COMPANY_NAME} can help {lead.company}. Is there anything else I can help you with?"
        )
    
    # Return missing fields
    missing = []
    if not lead.name: missing.append("name")
    if not lead.email: missing.append("email address")
    if not lead.company: missing.append("company name")
    if not lead.monthly_volume: missing.append("expected monthly transaction volume")
    if not lead.use_case: missing.append("primary use case")
    
    return f"LEAD_INCOMPLETE: Still need: {', '.join(missing)}. Please ask for the next field naturally."

# --- SDR Agent ---
class SDRAgent(Agent):
    """Sales Development Representative agent for FAQ and lead capture."""
    
    def __init__(self, llm) -> None:
        faq_list = "\n".join([f"- {faq['question']}" for faq in FAQ_DATA.get("faqs", [])])
        
        super().__init__(
            instructions=(
                f"You are an AI Sales Development Representative for {COMPANY_NAME}. "
                f"Your role is to answer questions and qualify leads for the sales team. "
                "\n\n"
                f"**GREETING:** Start with: 'Hi! I'm the AI assistant for {COMPANY_NAME}. "
                f"I can answer your questions about our payment solutions or connect you with our sales team. "
                f"How can I help you today?' "
                "\n\n"
                "**HANDLING QUESTIONS:**\n"
                "1. When the user asks a question, IMMEDIATELY call the search_faq tool with their question\n"
                "2. If FAQ_FOUND: Share the answer naturally and ask if they have more questions\n"
                "3. If FAQ_NOT_FOUND: Offer to connect them with sales and start lead capture\n"
                "\n"
                "**LEAD CAPTURE PROCESS:**\n"
                "When starting lead capture:\n"
                "1. Ask for information ONE field at a time\n"
                "2. After each response, call capture_lead with that field\n"
                "3. The tool will tell you what's still needed\n"
                "4. Continue until LEAD_COMPLETE\n"
                "\n"
                f"**AVAILABLE FAQs:**\n{faq_list}\n"
                "\n"
                "**TONE:** Professional but friendly. Be concise. Don't make up information not in FAQs."
            ),
            tools=[search_faq, capture_lead],
            llm=llm
        )

# --- Entrypoint ---
async def entrypoint(ctx: JobContext):
    """Main entrypoint."""
    
    # Initialize lead data
    lead_data = LeadData()
    
    ctx.log_context_fields = {"room": ctx.room.name}
    llm = google.LLM(model="gemini-2.5-flash")
    
    session = AgentSession(
        stt=deepgram.STT(model="nova-3"),
        llm=llm,
        tts=murf.TTS(
            voice="en-US-matthew",
            style="Conversation",
            tokenizer=tokenize.basic.SentenceTokenizer(min_sentence_len=2),
            text_pacing=True
        ),
        turn_detection=MultilingualModel(),
        vad=silero.VAD.load(),
        preemptive_generation=True,
    )
    
    session.userdata = {"lead": lead_data}
    
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
    await session.start(agent=SDRAgent(llm=llm), room=ctx.room)
    await ctx.connect()

def prewarm(proc: JobProcess):
    """Preload resources."""
    pass

if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint, prewarm_fnc=prewarm))
