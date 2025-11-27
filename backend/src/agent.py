import logging
import json
import os
from dataclasses import dataclass, field
from typing import Optional, Dict, Any
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

# --- Fraud Database ---
FRAUD_DB_FILE = "fraud_cases.json"

def load_fraud_database():
    """Load fraud cases from JSON database."""
    try:
        with open(FRAUD_DB_FILE, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        logger.error(f"Fraud database not found: {FRAUD_DB_FILE}")
        return {"cases": []}

def save_fraud_database(db_data):
    """Save fraud cases back to JSON database."""
    with open(FRAUD_DB_FILE, 'w') as f:
        json.dump(db_data, f, indent=2)
    logger.info("Fraud database updated")

# --- Session State ---
@dataclass
class FraudSession:
    """Tracks the fraud verification session state."""
    current_case: Optional[Dict[str, Any]] = None
    verification_passed: bool = False
    user_response: Optional[str] = None  # "yes" or "no" or "unknown"
    
    def is_verified(self) -> bool:
        return self.verification_passed
    
    def has_case(self) -> bool:
        return self.current_case is not None

# --- Tools ---
@function_tool
async def load_fraud_case(
    context: RunContext,
    user_name: str
) -> str:
    """
    Load a fraud case for a specific user.
    
    Args:
        user_name: The customer's name to look up the fraud case
    """
    session: FraudSession = context.userdata["fraud_session"]
    db = load_fraud_database()
    
    # Find case by username (case-insensitive)
    user_name_lower = user_name.lower()
    matching_case = None
    
    for case in db.get("cases", []):
        if case.get("userName", "").lower() == user_name_lower:
            matching_case = case
            break
    
    if not matching_case:
        return f"CASE_NOT_FOUND: No fraud case found for {user_name}. Please verify the name."
    
    # Check if already processed
    if matching_case.get("status") != "pending_review":
        return f"CASE_ALREADY_PROCESSED: This case was already resolved as {matching_case.get('status')}."
    
    # Load case into session
    session.current_case = matching_case
    context.userdata["fraud_session"] = session
    
    return (
        f"CASE_LOADED: Found fraud case for {matching_case['userName']}. "
        f"Card ending in {matching_case['cardEnding']}. "
        f"Now proceed with security verification using the security question."
    )

@function_tool
async def verify_customer(
    context: RunContext,
    security_answer: str
) -> str:
    """
    Verify the customer's identity using their security question answer.
    
    Args:
        security_answer: The customer's answer to the security question
    """
    session: FraudSession = context.userdata["fraud_session"]
    
    if not session.has_case():
        return "ERROR: No fraud case loaded. Please load a case first."
    
    case = session.current_case
    correct_answer = case.get("securityAnswer", "").lower().strip()
    user_answer = security_answer.lower().strip()
    
    if user_answer == correct_answer:
        session.verification_passed = True
        context.userdata["fraud_session"] = session
        
        return (
            f"VERIFICATION_PASSED: Identity confirmed. "
            f"Now read the suspicious transaction details and ask if the customer made this transaction."
        )
    else:
        session.verification_passed = False
        context.userdata["fraud_session"] = session
        
        # Update case status
        db = load_fraud_database()
        for case_item in db["cases"]:
            if case_item.get("userName") == case.get("userName"):
                case_item["status"] = "verification_failed"
                case_item["outcome"] = "Customer failed security verification."
                break
        save_fraud_database(db)
        
        return (
            f"VERIFICATION_FAILED: Security answer incorrect. "
            f"For your security, I cannot proceed. Please contact your bank branch directly. "
            f"This call will now end."
        )

@function_tool
async def record_transaction_response(
    context: RunContext,
    customer_made_transaction: bool
) -> str:
    """
    Record whether the customer confirms they made the suspicious transaction.
    
    Args:
        customer_made_transaction: True if customer confirms, False if they deny
    """
    session: FraudSession = context.userdata["fraud_session"]
    
    if not session.is_verified():
        return "ERROR: Customer not verified. Cannot record response."
    
    if not session.has_case():
        return "ERROR: No fraud case loaded."
    
    case = session.current_case
    db = load_fraud_database()
    
    # Find and update the case
    for case_item in db["cases"]:
        if case_item.get("userName") == case.get("userName"):
            if customer_made_transaction:
                case_item["status"] = "confirmed_safe"
                case_item["outcome"] = f"Customer confirmed the transaction of {case['transactionAmount']} to {case['transactionName']} was legitimate."
                session.user_response = "yes"
                
                return (
                    f"MARKED_SAFE: Transaction confirmed as legitimate. "
                    f"Thank the customer and inform them no further action is needed. "
                    f"Their card remains active."
                )
            else:
                case_item["status"] = "confirmed_fraud"
                case_item["outcome"] = f"Customer denied the transaction of {case['transactionAmount']} to {case['transactionName']}. Card has been blocked and dispute initiated."
                session.user_response = "no"
                
                return (
                    f"MARKED_FRAUD: Transaction confirmed as fraudulent. "
                    f"Inform the customer their card ending in {case['cardEnding']} has been blocked immediately. "
                    f"A new card will be issued within 5-7 business days. "
                    f"A fraud dispute has been filed and they will not be liable for this charge."
                )
            break
    
    save_fraud_database(db)
    context.userdata["fraud_session"] = session
    
    return "Case updated successfully."

# --- Fraud Alert Agent ---
class FraudAlertAgent(Agent):
    """Bank fraud detection voice agent."""
    
    def __init__(self, llm) -> None:
        super().__init__(
            instructions=(
                "You are a fraud alert agent for HDFC Bank's Fraud Detection Department. "
                "\n\n"
                "**GREETING:** Start by saying: 'Hello, this is HDFC Bank Fraud Detection Department. "
                "I'm calling about a suspicious transaction on your account. "
                "May I have your full name to look up your case?' "
                "\n\n"
                "**CALL FLOW:**\n"
                "1. **Get Name:** Ask for the customer's full name\n"
                "2. **Load Case:** Call load_fraud_case with their name\n"
                "3. **Security Verification:** "
                "   - Tell them you need to verify their identity\n"
                "   - Ask the security question from the loaded case\n"
                "   - Call verify_customer with their answer\n"
                "   - If VERIFICATION_FAILED: Apologize and end the call\n"
                "   - If VERIFICATION_PASSED: Continue to step 4\n"
                "4. **Read Transaction Details:** "
                "   - Explain you detected a suspicious transaction\n"
                "   - Read: amount, merchant name, time, location\n"
                "   - Ask: 'Did you make this transaction?'\n"
                "5. **Record Response:** "
                "   - If they say YES/confirm: Call record_transaction_response with True\n"
                "   - If they say NO/deny: Call record_transaction_response with False\n"
                "6. **Close Call:** "
                "   - If MARKED_SAFE: Thank them, no action needed\n"
                "   - If MARKED_FRAUD: Explain card blocked, new card coming, dispute filed\n"
                "   - Say goodbye\n"
                "\n"
                "**TONE:** Professional, calm, reassuring. Never ask for card numbers, PINs, or passwords.\n"
                "**IMPORTANT:** Always call tools at the right steps. Don't skip verification!"
            ),
            tools=[load_fraud_case, verify_customer, record_transaction_response],
            llm=llm
        )

# --- Entrypoint ---
async def entrypoint(ctx: JobContext):
    """Main entrypoint for fraud alert agent."""
    
    # Initialize session
    fraud_session = FraudSession()
    
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
    
    session.userdata = {"fraud_session": fraud_session}
    
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
    await session.start(agent=FraudAlertAgent(llm=llm), room=ctx.room)
    await ctx.connect()

def prewarm(proc: JobProcess):
    """Preload resources."""
    pass

if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint, prewarm_fnc=prewarm))

