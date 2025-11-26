import logging
import json
import os
import asyncio
from datetime import datetime, timedelta
from typing import Annotated, Literal, Optional, Dict, List
from dataclasses import dataclass, field

print("\n" + "=" * 50)
print("Razorpay SDR Agent")
print("agent.py LOADED SUCCESSFULLY!")
print("=" * 50 + "\n")

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

FAQ_FILE = "razorpay_faq.json"
LEADS_FILE = "leads.json"
MEETINGS_FILE = "meetings.json"
CALL_NOTES_FILE = "call_notes.json"
EMAILS_FILE = "follow_up_emails.json"

def load_faq() -> Dict:
    """Load Razorpay FAQ data"""
    try:
        path = os.path.join(os.path.dirname(__file__), FAQ_FILE)
        with open(path, "r", encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading FAQ: {e}")
        return {"company": {}, "faq": []}

def save_lead(lead_data: Dict):
    """Save lead data to JSON file"""
    try:
        path = os.path.join(os.path.dirname(__file__), LEADS_FILE)
        leads = []
        
        if os.path.exists(path):
            with open(path, "r", encoding='utf-8') as f:
                leads = json.load(f)
        
        leads.append(lead_data)
        
        with open(path, "w", encoding='utf-8') as f:
            json.dump(leads, f, indent=2)
        
        print(f"Lead saved: {lead_data.get('name', 'Unknown')}")
    except Exception as e:
        print(f"Error saving lead: {e}")

FAQ_DATA = load_faq()

@dataclass
class LeadInfo:
    name: str = ""
    company: str = ""
    email: str = ""
    role: str = ""
    use_case: str = ""
    team_size: str = ""
    timeline: str = ""
    
    def is_complete(self) -> bool:
        return all([self.name, self.company, self.email, self.role])

@dataclass
class SDRState:
    lead: LeadInfo = field(default_factory=LeadInfo)
    conversation_stage: Literal["greeting", "discovery", "faq", "qualification", "closing"] = "greeting"
    call_ended: bool = False
    persona: str = "unknown"
    conversation_transcript: List[str] = field(default_factory=list)
    pain_points: List[str] = field(default_factory=list)

@dataclass
class Userdata:
    sdr_state: SDRState
    agent_session: Optional[AgentSession] = None

@function_tool
async def search_faq(
    ctx: RunContext[Userdata],
    query: Annotated[str, Field(description="User's question about Razorpay")]
) -> str:
    """Search FAQ for relevant answers about Razorpay"""
    query_lower = query.lower()
    
    for faq_item in FAQ_DATA["faq"]:
        question = faq_item["question"].lower()
        answer = faq_item["answer"]
        
        # Simple keyword matching
        if any(word in question for word in query_lower.split()) or any(word in query_lower for word in question.split()):
            return f"Based on our FAQ: {answer}"
    
    # If no direct match, return general company info
    company = FAQ_DATA["company"]
    return f"I'd be happy to help! {company['description']}. Could you be more specific about what you'd like to know about Razorpay?"

@function_tool
async def collect_lead_info(
    ctx: RunContext[Userdata],
    field: Annotated[str, Field(description="The field to update: name, company, email, role, use_case, team_size, or timeline")],
    value: Annotated[str, Field(description="The value provided by the user")]
) -> str:
    """Collect and store lead information"""
    state = ctx.userdata.sdr_state
    
    if hasattr(state.lead, field):
        setattr(state.lead, field, value)
        print(f"Updated {field}: {value}")
        
        # Check what's still needed
        missing = []
        if not state.lead.name: missing.append("name")
        if not state.lead.company: missing.append("company")
        if not state.lead.email: missing.append("email")
        if not state.lead.role: missing.append("role")
        
        if missing:
            return f"Got it! I still need your {', '.join(missing)}."
        else:
            return "Perfect! I have all the key information. Is there anything else about Razorpay you'd like to know?"
    
    return "I couldn't update that information. Please try again."

@function_tool
async def book_meeting(
    ctx: RunContext[Userdata],
    preferred_time: Annotated[str, Field(description="User's preferred meeting time (e.g., 'tomorrow 2pm', 'next week')")] = ""
) -> str:
    """Book a demo meeting with available time slots"""
    # Mock available slots
    now = datetime.now()
    slots = [
        (now + timedelta(days=1)).strftime("%Y-%m-%d 2:00 PM"),
        (now + timedelta(days=2)).strftime("%Y-%m-%d 10:00 AM"),
        (now + timedelta(days=3)).strftime("%Y-%m-%d 3:00 PM")
    ]
    
    if not preferred_time:
        return f"I'd love to schedule a demo! Here are some available slots: {', '.join(slots)}. Which works best for you?"
    
    # Book the meeting
    lead = ctx.userdata.sdr_state.lead
    meeting_data = {
        "name": lead.name,
        "email": lead.email,
        "company": lead.company,
        "requested_time": preferred_time,
        "booked_slot": slots[0],  # Default to first slot
        "timestamp": datetime.now().isoformat()
    }
    
    try:
        path = os.path.join(os.path.dirname(__file__), MEETINGS_FILE)
        meetings = []
        if os.path.exists(path):
            with open(path, "r") as f:
                meetings = json.load(f)
        meetings.append(meeting_data)
        with open(path, "w") as f:
            json.dump(meetings, f, indent=2)
    except Exception as e:
        print(f"Error saving meeting: {e}")
    
    return f"Perfect! I've booked your demo for {meeting_data['booked_slot']}. You'll receive a calendar invite at {lead.email}."

@function_tool
async def detect_persona(
    ctx: RunContext[Userdata],
    user_message: Annotated[str, Field(description="User's recent message to analyze for persona")]
) -> str:
    """Detect user persona and adapt pitch"""
    state = ctx.userdata.sdr_state
    msg_lower = user_message.lower()
    
    # Simple persona detection
    if any(word in msg_lower for word in ["code", "api", "integrate", "developer", "technical"]):
        state.persona = "developer"
        return "I can see you're technically focused! Let me highlight Razorpay's developer-friendly features: easy API integration, comprehensive SDKs, and detailed documentation."
    elif any(word in msg_lower for word in ["product", "feature", "roadmap", "user"]):
        state.persona = "product_manager"
        return "As a product person, you'll appreciate our feature-rich platform, analytics dashboard, and how we help improve conversion rates."
    elif any(word in msg_lower for word in ["founder", "startup", "business", "growth"]):
        state.persona = "founder"
        return "Perfect! As a founder, you need reliable payments that scale. Razorpay handles everything from small transactions to enterprise volumes."
    else:
        state.persona = "business_user"
        return "I'll focus on how Razorpay can streamline your payment processes and improve your business operations."

@function_tool
async def track_pain_point(
    ctx: RunContext[Userdata],
    pain_point: Annotated[str, Field(description="A business challenge or pain point mentioned by the user")]
) -> str:
    """Track user's pain points for better qualification"""
    state = ctx.userdata.sdr_state
    state.pain_points.append(pain_point)
    return f"I understand that {pain_point} is a challenge for you. Let me explain how Razorpay addresses this specific issue."

@function_tool
async def check_returning_visitor(
    ctx: RunContext[Userdata],
    email: Annotated[str, Field(description="User's email to check against previous leads")]
) -> str:
    """Check if user is a returning visitor"""
    try:
        path = os.path.join(os.path.dirname(__file__), LEADS_FILE)
        if os.path.exists(path):
            with open(path, "r") as f:
                leads = json.load(f)
            
            for lead in leads:
                if lead.get("email", "").lower() == email.lower():
                    return f"Welcome back! I see you were interested in {lead.get('use_case', 'our payment solutions')} last time. How can I help you today?"
    except Exception as e:
        print(f"Error checking returning visitor: {e}")
    
    return "Great to meet you! I don't see any previous conversations, so let's start fresh."

@function_tool
async def end_call_summary(
    ctx: RunContext[Userdata]
) -> str:
    """Generate end-of-call summary and save lead"""
    state = ctx.userdata.sdr_state
    lead = state.lead
    
    # Save to JSON
    lead_data = {
        "name": lead.name,
        "company": lead.company,
        "email": lead.email,
        "role": lead.role,
        "use_case": lead.use_case,
        "team_size": lead.team_size,
        "timeline": lead.timeline,
        "timestamp": asyncio.get_event_loop().time()
    }
    
    save_lead(lead_data)
    state.call_ended = True
    
    summary = f"Thank you {lead.name}! Here's a quick summary: You're {lead.role} at {lead.company}, interested in {lead.use_case or 'our payment solutions'}. "
    
    if lead.timeline:
        summary += f"Timeline: {lead.timeline}. "
    
    summary += "I'll make sure our team follows up with you soon. Have a great day!"
    
    # Generate call notes and qualification score
    call_notes = {
        "lead_info": lead_data,
        "persona": state.persona,
        "pain_points": state.pain_points,
        "decision_maker": "yes" if "founder" in lead.role.lower() or "ceo" in lead.role.lower() else "unknown",
        "budget_mentioned": "no",  # Could be enhanced with transcript analysis
        "urgency": "medium" if lead.timeline else "low",
        "fit_score": 75 if lead.is_complete() else 45,
        "notes": f"Interested in {lead.use_case}. {state.persona} persona detected.",
        "timestamp": datetime.now().isoformat()
    }
    
    # Save call notes
    try:
        path = os.path.join(os.path.dirname(__file__), CALL_NOTES_FILE)
        notes = []
        if os.path.exists(path):
            with open(path, "r") as f:
                notes = json.load(f)
        notes.append(call_notes)
        with open(path, "w") as f:
            json.dump(notes, f, indent=2)
    except Exception as e:
        print(f"Error saving call notes: {e}")
    
    # Generate follow-up email
    email_draft = {
        "to": lead.email,
        "subject": f"Great connecting with you, {lead.name}!",
        "body": f"Hi {lead.name},\n\nThanks for taking the time to learn about Razorpay today! Based on our conversation, I understand you're looking for {lead.use_case or 'payment solutions'} for {lead.company}.\n\nAs discussed, Razorpay can help streamline your payment processes with our easy integration and competitive pricing. I'd love to show you a quick demo of how other companies like yours are using our platform.\n\nWould you be available for a 15-minute call this week?\n\nBest regards,\nRazorpay Sales Team",
        "timestamp": datetime.now().isoformat()
    }
    
    # Save email draft
    try:
        path = os.path.join(os.path.dirname(__file__), EMAILS_FILE)
        emails = []
        if os.path.exists(path):
            with open(path, "r") as f:
                emails = json.load(f)
        emails.append(email_draft)
        with open(path, "w") as f:
            json.dump(emails, f, indent=2)
    except Exception as e:
        print(f"Error saving email draft: {e}")
    
    return summary

class RazorpaySDRAgent(Agent):
    def __init__(self):
        super().__init__(
            instructions=f"""
            You are a friendly Sales Development Representative (SDR) for Razorpay, India's leading payment gateway company.
            
            🎯 **YOUR ROLE:**
            - Greet visitors warmly and ask what brought them here
            - Understand their business needs and use case
            - Answer questions about Razorpay using the FAQ tool
            - Collect key lead information naturally during conversation
            - Provide helpful, accurate information about our payment solutions
            
            📋 **LEAD QUALIFICATION:**
            Always try to collect: name, company, email, role, use case, team size, timeline
            
            🏢 **ABOUT RAZORPAY:**
            {FAQ_DATA["company"]["description"]}
            
            💬 **CONVERSATION STYLE:**
            - Be conversational and helpful, not pushy
            - Ask open-ended questions about their business
            - Use search_faq for product/pricing questions
            - Use detect_persona to adapt your pitch based on their role
            - Use collect_lead_info to store responses
            - Use check_returning_visitor if they provide email
            - Offer to book_meeting for interested prospects
            - Use end_call_summary when they're ready to end
            
            Start by greeting them and asking what brought them to learn about Razorpay today.
            """,
            tools=[search_faq, collect_lead_info, book_meeting, detect_persona, track_pain_point, check_returning_visitor, end_call_summary],
        )

def prewarm(proc: JobProcess):
    proc.userdata["vad"] = silero.VAD.load()

async def entrypoint(ctx: JobContext):
    ctx.log_context_fields = {"room": ctx.room.name}

    print("\n" + "=" * 25)
    print("STARTING RAZORPAY SDR SESSION")
    print(f"Loaded {len(FAQ_DATA['faq'])} FAQ entries")
    
    userdata = Userdata(sdr_state=SDRState())

    session = AgentSession(
        stt=deepgram.STT(model="nova-3"),
        llm=google.LLM(model="gemini-2.5-flash"),
        tts=murf.TTS(
            voice="en-US-matthew", 
            style="Conversational",        
            text_pacing=True,
        ),
        turn_detection=MultilingualModel(),
        vad=ctx.proc.userdata["vad"],
        userdata=userdata,
    )
    
    userdata.agent_session = session
    
    await session.start(
        agent=RazorpaySDRAgent(),
        room=ctx.room,
        room_input_options=RoomInputOptions(
            noise_cancellation=noise_cancellation.BVC()
        ),
    )

    await ctx.connect()

if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint, prewarm_fnc=prewarm))