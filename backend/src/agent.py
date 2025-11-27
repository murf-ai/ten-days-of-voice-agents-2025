# ======================================================
# 🏦 DAY 6: BANK FRAUD ALERT AGENT
# 🛡️ "Global Bank" - Fraud Detection & Resolution
# 🚀 Features: Identity Verification, Database Lookup, Status Updates
# ======================================================

import logging
import json
import os
from datetime import datetime
from typing import Annotated, Optional, List
from dataclasses import dataclass, asdict

print("\n" + "🛡️" * 50)
print("🚀 BANK FRAUD AGENT BY DR ABHISHEK - INITIALIZED")
print("📚 TASKS: Verify Identity -> Check Transaction -> Update DB")
print("🛡️" * 50 + "\n")

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

# 🔌 PLUGINS
from livekit.plugins import murf, silero, google, deepgram, noise_cancellation
from livekit.plugins.turn_detector.multilingual import MultilingualModel

logger = logging.getLogger("agent")
load_dotenv(".env.local")

# ======================================================
# 💾 1. DATABASE SETUP (Mock Data)
# ======================================================

DB_FILE = "fraud_db.json"

# Schema as requested
@dataclass
class FraudCase:
    userName: str
    securityIdentifier: str
    cardEnding: str
    transactionName: str
    transactionAmount: str
    transactionTime: str
    transactionSource: str
    # Internal status fields
    case_status: str = "pending_review"  # pending_review, confirmed_safe, confirmed_fraud
    notes: str = ""

def seed_database():
    """Creates a sample database if one doesn't exist."""
    path = os.path.join(os.path.dirname(__file__), DB_FILE)
    if not os.path.exists(path):
        sample_data = [
            {
                "userName": "John",
                "securityIdentifier": "12345",
                "cardEnding": "4242",
                "transactionName": "ABC Industry",
                "transactionAmount": "$450.00",
                "transactionTime": "2:30 AM EST",
                "transactionSource": "alibaba.com",
                "case_status": "pending_review",
                "notes": "Automated flag: High value transaction."
            },
            {
                "userName": "Sarah",
                "securityIdentifier": "99887",
                "cardEnding": "1199",
                "transactionName": "Unknown Crypto Exchange",
                "transactionAmount": "$2,100.00",
                "transactionTime": "4:15 AM PST",
                "transactionSource": "online_transfer",
                "case_status": "pending_review",
                "notes": "Automated flag: Unusual location."
            }
        ]
        with open(path, "w", encoding='utf-8') as f:
            json.dump(sample_data, f, indent=4)
        print(f"✅ Database seeded at {DB_FILE}")

# Initialize DB on load
seed_database()

# ======================================================
# 🧠 2. STATE MANAGEMENT
# ======================================================

@dataclass
class Userdata:
    # Holds the specific case currently being discussed
    active_case: Optional[FraudCase] = None

# ======================================================
# 🛠️ 3. FRAUD AGENT TOOLS
# ======================================================

@function_tool
async def lookup_customer(
    ctx: RunContext[Userdata],
    name: Annotated[str, Field(description="The name the user provides")]
) -> str:
    """
    🔍 Looks up a customer in the fraud database by name.
    Call this immediately when the user says their name.
    """
    print(f"🔎 LOOKING UP: {name}")
    path = os.path.join(os.path.dirname(__file__), DB_FILE)
    
    try:
        with open(path, "r") as f:
            data = json.load(f)
            
        # Case-insensitive search
        found_record = next((item for item in data if item["userName"].lower() == name.lower()), None)
        
        if found_record:
            # Load into session state
            ctx.userdata.active_case = FraudCase(**found_record)
            
            # Return info to the LLM so it can verify the user
            return (f"Record Found. \n"
                    f"User: {found_record['userName']}\n"
                    f"Security ID (Expected): {found_record['securityIdentifier']}\n"
                    f"Transaction Details: {found_record['transactionAmount']} at {found_record['transactionName']} ({found_record['transactionSource']})\n"
                    f"Instructions: Ask the user for their 'Security Identifier' to verify identity before discussing the transaction.")
        else:
            return "User not found in the fraud database. Ask them to repeat the name or contact support manually."
            
    except Exception as e:
        return f"Database error: {str(e)}"

@function_tool
async def resolve_fraud_case(
    ctx: RunContext[Userdata],
    status: Annotated[str, Field(description="The final status: 'confirmed_safe' or 'confirmed_fraud'")],
    notes: Annotated[str, Field(description="A brief summary of the user's response")]
) -> str:
    """
    💾 Saves the result of the investigation to the database.
    Call this after the user confirms or denies the transaction.
    """
    if not ctx.userdata.active_case:
        return "Error: No active case selected."

    # Update local object
    case = ctx.userdata.active_case
    case.case_status = status
    case.notes = notes
    
    # Update Database File
    path = os.path.join(os.path.dirname(__file__), DB_FILE)
    try:
        with open(path, "r") as f:
            data = json.load(f)
        
        # Find index and update
        for i, item in enumerate(data):
            if item["userName"] == case.userName:
                data[i] = asdict(case)
                break
        
        with open(path, "w") as f:
            json.dump(data, f, indent=4)
            
        print(f"✅ CASE UPDATED: {case.userName} -> {status}")
        
        if status == "confirmed_fraud":
            return "Case updated as FRAUD. Inform the user: Card ending in " + case.cardEnding + " is now blocked. A new card will be mailed."
        else:
            return "Case updated as SAFE. Inform the user: The restriction has been lifted. Thank you for verifying."

    except Exception as e:
        return f"Error saving to DB: {e}"

# ======================================================
# 🤖 4. AGENT DEFINITION
# ======================================================

class FraudAgent(Agent):
    def __init__(self):
        super().__init__(
            instructions="""
            You are 'Alex', a Fraud Detection Specialist at Global Bank. 
            Your job is to verify a suspicious transaction with the customer efficiently and professionally.

            🛡️ **SECURITY PROTOCOL (FOLLOW STRICTLY):**
            
            1. **GREETING & ID:** - State that you are calling about a "security alert".
               - Ask: "Am I speaking with the account holder? May I have your first name?"
            
            2. **LOOKUP:**
               - Use tool `lookup_customer` immediately when you hear the name.
            
            3. **VERIFICATION:**
               - Once the record is loaded, ask for their **Security Identifier**.
               - Compare their answer to the data returned by the tool.
               - IF WRONG: Politely apologize and disconnect (pretend to end call).
               - IF CORRECT: Proceed.
            
            4. **TRANSACTION REVIEW:**
               - Read the transaction details clearly: "We flagged a charge of [Amount] at [Merchant] on [Time]."
               - Ask: "Did you make this transaction?"
            
            5. **RESOLUTION:**
               - **If User Says YES (Legit):** Use tool `resolve_fraud_case(status='confirmed_safe')`.
               - **If User Says NO (Fraud):** Use tool `resolve_fraud_case(status='confirmed_fraud')`.
            
            6. **CLOSING:**
               - Confirm the action taken (Card blocked OR Unblocked).
               - Say goodbye professionally.

            ⚠️ **TONE:** Calm, authoritative, reassuring. Do NOT ask for full card numbers or passwords.
            """,
            tools=[lookup_customer, resolve_fraud_case],
        )

# ======================================================
# 🎬 ENTRYPOINT
# ======================================================

def prewarm(proc: JobProcess):
    proc.userdata["vad"] = silero.VAD.load()

async def entrypoint(ctx: JobContext):
    ctx.log_context_fields = {"room": ctx.room.name}

    print("\n" + "💼" * 25)
    print("🚀 STARTING FRAUD ALERT SESSION")
    
    # 1. Initialize State
    userdata = Userdata()

    # 2. Setup Agent
    session = AgentSession(
        stt=deepgram.STT(model="nova-3"),
        llm=google.LLM(model="gemini-2.5-flash"), # Ensure you have access to this model version
        tts=murf.TTS(
            voice="en-US-marcus", # A serious, professional male voice
            style="Conversational",        
            text_pacing=True,
        ),
        turn_detection=MultilingualModel(),
        vad=ctx.proc.userdata["vad"],
        userdata=userdata,
    )
    
    # 3. Start
    await session.start(
        agent=FraudAgent(),
        room=ctx.room,
        room_input_options=RoomInputOptions(
            noise_cancellation=noise_cancellation.BVC()
        ),
    )

    await ctx.connect()

if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint, prewarm_fnc=prewarm))