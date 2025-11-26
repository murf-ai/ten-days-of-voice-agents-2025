import logging
import json
from pathlib import Path
from datetime import datetime
from typing import Optional

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

# ------------ Company FAQ & Content Management ------------

FAQ_FILE = Path(__file__).parent.parent / "shared-data" / "day5_company_faq.json"
LEADS_FILE = Path(__file__).parent.parent / "leads_captured.json"

class CompanyKnowledgeBase:
    def __init__(self):
        self.data = self._load_faq()
        self.company_name = self.data.get("company", {}).get("name", "our company")
    
    def _load_faq(self):
        """Load company FAQ and content from JSON file"""
        if not FAQ_FILE.exists():
            logger.error(f"FAQ file not found: {FAQ_FILE}")
            FAQ_FILE.parent.mkdir(parents=True, exist_ok=True)
            # Create minimal default
            default_data = {
                "company": {
                    "name": "Razorpay",
                    "tagline": "India's Leading Payment Gateway",
                    "description": "Payment solutions for businesses"
                },
                "faqs": [
                    {
                        "question": "What does Razorpay do?",
                        "answer": "Razorpay helps businesses accept online payments easily."
                    }
                ]
            }
            with open(FAQ_FILE, "w") as f:
                json.dump(default_data, f, indent=2)
            return default_data
        
        try:
            with open(FAQ_FILE, "r") as f:
                return json.load(f)
        except json.JSONDecodeError as e:
            logger.error(f"Error parsing FAQ file: {e}")
            return {"company": {}, "faqs": []}
    
    def search_faq(self, query: str) -> Optional[dict]:
        """Simple keyword-based FAQ search"""
        query_lower = query.lower()
        
        # Search through FAQs
        for faq in self.data.get("faqs", []):
            question = faq.get("question", "").lower()
            answer = faq.get("answer", "").lower()
            
            # Check if query keywords match question or answer
            if any(word in question for word in query_lower.split()) or \
               any(word in query_lower for word in question.split()):
                return faq
        
        return None
    
    def get_company_intro(self) -> str:
        """Get company introduction"""
        company = self.data.get("company", {})
        return f"{company.get('name', 'Our company')} - {company.get('tagline', '')}. {company.get('description', '')}"
    
    def get_products_summary(self) -> str:
        """Get summary of products"""
        products = self.data.get("products", [])
        if not products:
            return "We offer various solutions for businesses."
        
        summary = "Our main products include: "
        summary += ", ".join([p.get("name", "") for p in products[:3]])
        return summary
    
    def get_pricing_info(self) -> str:
        """Get pricing information"""
        pricing = self.data.get("pricing", {})
        if not pricing:
            return "Please contact us for pricing details."
        
        pg_pricing = pricing.get("payment_gateway", {})
        return f"Our payment gateway charges {pg_pricing.get('transaction_fee', 'competitive rates')} with {pg_pricing.get('setup_fee', 'no setup fee')}."

# ------------ Lead Capture State ------------

class LeadData:
    def __init__(self):
        self.data = {
            "name": "",
            "company": "",
            "email": "",
            "role": "",
            "use_case": "",
            "team_size": "",
            "timeline": "",
            "notes": "",
            "captured_at": ""
        }
    
    def is_complete(self) -> bool:
        """Check if minimum required fields are filled"""
        required = ["name", "company", "email", "use_case"]
        return all(self.data.get(field) for field in required)
    
    def missing_fields(self) -> list:
        """Get list of missing required fields"""
        required = ["name", "company", "email", "use_case"]
        return [field for field in required if not self.data.get(field)]
    
    def to_dict(self) -> dict:
        """Convert to dictionary"""
        return {**self.data, "captured_at": datetime.now().isoformat()}

# ------------ Lead Storage ------------

class LeadStorage:
    @staticmethod
    def save_lead(lead_data: dict):
        """Save lead to JSON file"""
        # Load existing leads
        if LEADS_FILE.exists():
            try:
                with open(LEADS_FILE, "r") as f:
                    leads = json.load(f)
            except json.JSONDecodeError:
                leads = []
        else:
            LEADS_FILE.parent.mkdir(parents=True, exist_ok=True)
            leads = []
        
        # Add new lead
        leads.append(lead_data)
        
        # Save back to file
        with open(LEADS_FILE, "w") as f:
            json.dump(leads, f, indent=2)
        
        logger.info(f"Lead saved: {lead_data.get('name')} from {lead_data.get('company')}")

# ------------ SDR Agent ------------

class SDRAgent(Agent):
    """Sales Development Representative voice agent"""
    def __init__(self, knowledge_base: CompanyKnowledgeBase):
        self.kb = knowledge_base
        self.lead = LeadData()
        self.conversation_stage = "greeting"
        
        company_intro = knowledge_base.get_company_intro()
        products_summary = knowledge_base.get_products_summary()
        
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
    """Prewarm function to load models and data before agent starts"""
    proc.userdata["vad"] = silero.VAD.load()
    
    # Preload FAQ data
    knowledge_base = CompanyKnowledgeBase()
    proc.userdata["knowledge_base"] = knowledge_base
    logger.info(f"Prewarmed with FAQ for {knowledge_base.company_name}")

async def entrypoint(ctx: JobContext):
    # Logging setup
    ctx.log_context_fields = {
        "room": ctx.room.name,
    }
    
    logger.info("🚀 Starting SDR Agent...")
    
    # Load knowledge base from prewarm or create new
    if "knowledge_base" in ctx.proc.userdata:
        knowledge_base = ctx.proc.userdata["knowledge_base"]
        logger.info(f"Using prewarmed knowledge base for {knowledge_base.company_name}")
    else:
        knowledge_base = CompanyKnowledgeBase()
        logger.info(f"Created new knowledge base for {knowledge_base.company_name}")

    # Voice agent session pipeline
    session = AgentSession(
        stt=deepgram.STT(model="nova-3"),
        llm=google.LLM(model="gemini-2.5-flash"),
        tts=murf.TTS(
            voice="Iris",  # Professional, friendly voice for SDR
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

    # Start session with SDR Agent
    logger.info("🎙️ Starting SDR agent session...")
    await session.start(
        agent=SDRAgent(knowledge_base),
        room=ctx.room,
        room_input_options=RoomInputOptions(
            noise_cancellation=noise_cancellation.BVC(),
        ),
    )

    logger.info("🔗 Connecting to room...")
    await ctx.connect()
    logger.info(f"✅ SDR Agent for {knowledge_base.company_name} connected successfully!")

if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint, prewarm_fnc=prewarm))
