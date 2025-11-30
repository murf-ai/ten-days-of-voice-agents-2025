import os
import json
import logging
from datetime import datetime
from typing import Dict, Any, List

# --- ADD ASYNCIO IMPORT HERE ---
import asyncio 

from dotenv import load_dotenv

# LiveKit Agent imports
from livekit.agents import (
    Agent,
    AgentSession,
    JobContext,
    RunContext,
    WorkerOptions,
    cli,
    function_tool,
)
# REMOVE THE BROKEN IMPORT BELOW
# from livekit.plugins.turn_detector.multilingual import MultilingualModel 
# FIX: The imports below are correct if the plugins are installed
from livekit.plugins import google, murf, deepgram, silero
from livekit.plugins.turn_detector.multilingual import MultilingualModel # Keep this import if you need MultilingualModel

load_dotenv(".env.local")
logger = logging.getLogger("sdr.agent")

# --- Configuration & File Paths (Adapted for LiveKit Structure) ---
KNOWLEDGE_FILE = 'Day5/SDRProject/Havells_india_lmt_faq_data.json'
OUTPUT_FILE = 'Day5/SDRProject/leads_output.json'
VOICE_SDR = "Anusha" 

# --- Helper Functions (SDR Backend Logic) ---

def load_knowledge_base(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        logger.error(f"Knowledge base file not found at {file_path}.")
        return None

def find_faq_answer_sync(user_query, knowledge_base):
    query = user_query.lower()
    
    if any(k in query for k in ["who", "for whom", "audience", "customer"]):
        return f"Razorpay is for **{knowledge_base.get('target_audience', 'Indian businesses of all sizes')}**."

    for entry in knowledge_base.get('faq_and_pricing', []):
        if any(keyword in query for keyword in entry.get('keywords', [])):
            return entry['answer']
    
    return None

def save_lead_data_sync(lead_data):
    try:
        if os.path.exists(OUTPUT_FILE):
            with open(OUTPUT_FILE, 'r+') as f:
                file_data = json.load(f)
                file_data['leads'].append(lead_data)
                f.seek(0)
                json.dump(file_data, f, indent=4)
                f.truncate()
        else:
            with open(OUTPUT_FILE, 'w') as f:
                json.dump({'leads': [lead_data]}, f, indent=4)
        logger.info(f"Lead data successfully saved to {OUTPUT_FILE}")
    except Exception as e:
        logger.error(f"Could not save lead data: {e}", exc_info=True)

# --- LLM Tools for SDR Logic ---

@function_tool
async def lookup_faq(ctx: RunContext[dict], user_query: str):
    """
    Searches the Razorpay knowledge base for answers to product, pricing, or audience questions.
    """
    knowledge_base = load_knowledge_base(KNOWLEDGE_FILE)
    if not knowledge_base:
        return {"response": "The knowledge base is currently unavailable.", "status": "error"}
    
    # REPLACED fwd_to_async WITH asyncio.to_thread
    answer = await asyncio.to_thread(find_faq_answer_sync, user_query, knowledge_base)
    
    if answer:
        return {"response": answer, "status": "answered"}
    
    return {"response": "That's a good question. I don't have that specific detail in my basic FAQ, but I can ensure a specialist follows up with you. Would you like me to collect your details?", "status": "unanswered"}


@function_tool
async def capture_and_save_lead(ctx: RunContext[dict], name: str, email: str, company: str, role: str, use_case: str, timeline: str):
    """
    Called when the conversation concludes. It saves the final lead data collected by the LLM.
    """
    lead_data = {
        "name": name,
        "email": email,
        "company": company,
        "role": role,
        "use_case": use_case,
        "timeline": timeline,
        "timestamp": datetime.now().isoformat()
    }
    
    # REPLACED fwd_to_async WITH asyncio.to_thread
    await asyncio.to_thread(save_lead_data_sync, lead_data)
    
    return {
        "status": "success", 
        "verbal_summary": f"I appreciate your time today! We have recorded {name} from {company}. Your primary interest is {use_case} and your timeline is {timeline}. I will ensure a specialist follows up with you via {email} shortly. Have a great day!"
    }


# --- The SDR Agent Class ---

class SDRAgent(Agent):
    """Razorpay SDR Agent for FAQ and Lead Capture."""
    def __init__(self):
        instructions = f"""You are DISHA, a highly professional, warm, and focused Sales Development Representative (SDR) for Havells India Limited.
        
        GOAL: Your primary goal is qualification by answering FAQs and collecting 6 key lead details: Name, Email, Company, Role, Use Case, and Timeline.
        
        1. GREETING: Start with the warm greeting script.
        2. DISCOVERY: Ask open-ended questions to learn the user's business needs and gently collect the 6 required details during discovery.
        3. FAQ HANDLING: If the user asks about the product, pricing, or audience, use the `lookup_faq` tool immediately. Present the tool's response clearly.
        4. CLOSURE: When the user says they are done, IMMEDIATELY call the `capture_and_save_lead` tool, passing ALL 6 collected details (even if some are 'N/A'). Speak only the verbal_summary returned by the tool's message, and then disconnect the call."""

        super().__init__(
            instructions=instructions,
            tools=[
                lookup_faq,
                capture_and_save_lead,
            ]
        )

# --- LiveKit Entrypoint ---

async def entrypoint(ctx: JobContext):
    logger.info("Starting SDR Agent")

    # Initialize the LLM, STT, and TTS components
    session = AgentSession(
        stt=deepgram.STT(model="nova-3"),
        llm=google.LLM(model="gemini-2.5-flash", api_key=os.getenv("GOOGLE_API_KEY")),
        tts=murf.TTS(voice=VOICE_SDR, style="Conversation", text_pacing=True),
        turn_detection=MultilingualModel(),
        vad=silero.VAD.load(),
    )

    # Create and start the SDR agent
    agent = SDRAgent()
    await session.start(agent=agent, room=ctx.room)
    await ctx.connect()


if __name__ == "__main__":
    # Ensure the leads output file is initialized correctly before starting
    if not os.path.exists(OUTPUT_FILE):
        try:
            with open(OUTPUT_FILE, 'w') as f:
                json.dump({'leads': []}, f)
        except Exception as e:
            print(f"CRITICAL ERROR: Could not create output file {OUTPUT_FILE}: {e}")
            exit()
            
    # Run the worker to listen for incoming job requests
    cli.run_app(
        WorkerOptions(
            entrypoint_fnc=entrypoint,
        )
    )