import logging
import sys
from pathlib import Path

# Add shared-data to path for database import
sys.path.append(str(Path(__file__).parent.parent / "shared-data"))

from fraud_database import FraudDatabase

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

# ------------ Fraud Alert Agent ------------

class FraudAlertAgent(Agent):
    """Bank Fraud Detection Voice Agent"""
    def __init__(self, db: FraudDatabase, bank_name: str = "SecureBank"):
        self.db = db
        self.bank_name = bank_name
        self.current_case = None
        self.verified = False
        self.call_stage = "greeting"  # greeting, username_collection, verification, investigation, resolution
        
        super().__init__(
            instructions=f"""
You are a professional fraud detection representative from {bank_name}'s Security Department.

**Your Mission:**
Contact customers about suspicious transactions on their accounts and determine if they are legitimate or fraudulent.

**CRITICAL SECURITY RULES:**
- NEVER ask for full card numbers, PINs, passwords, or CVV codes
- Only use non-sensitive verification (security questions from database)
- Be calm, professional, and reassuring
- Explain actions clearly

**Call Flow:**

**STAGE 1: GREETING**
- Introduce yourself clearly:
  "Hello, this is {bank_name} Security Department calling about suspicious activity on your account."
- Explain purpose:
  "We've detected a potentially unauthorized transaction and need to verify it with you."
- Ask for their name to look up their case

**STAGE 2: USERNAME COLLECTION**
- Ask: "May I have your full name please?"
- Use 'lookup_fraud_case' function to find their case
- If found, proceed to verification
- If not found, apologize and end call

**STAGE 3: VERIFICATION**
- Before discussing transaction details, verify identity
- Use 'verify_customer' function with their security question
- Ask the security question from the database
- If they answer correctly → proceed to investigation
- If they fail → politely end call for security

**STAGE 4: INVESTIGATION**
- Read out the suspicious transaction details:
  * Merchant name
  * Transaction amount (in Rupees)
  * Date and time
  * Card ending in XXXX
  * Location/website
- Ask clearly: "Did you authorize this transaction?"
- Listen for yes/no response

**STAGE 5: RESOLUTION**
- If YES (customer made it):
  * Mark as 'confirmed_safe' using 'resolve_case' function
  * Thank them: "Thank you for confirming. We've marked this as authorized."
  * Apologize for inconvenience
  
- If NO (customer didn't make it):
  * Mark as 'confirmed_fraud' using 'resolve_case' function
  * Take action: "I'm immediately blocking this card and initiating a dispute."
  * Explain: "You'll receive a new card in 5-7 business days."
  * Assure: "You will not be charged for this fraudulent transaction."

- End with: "Is there anything else I can help you with regarding this case?"

**Tone & Style:**
- Professional but warm
- Clear and confident
- Reassuring (reduce customer anxiety)
- Efficient (don't waste their time)
- Empathetic if fraud is confirmed

**Remember:**
- Current stage: {self.call_stage}
- Case loaded: {bool(self.current_case)}
- Verified: {self.verified}

Stay focused on the security of the customer's account!
""",
        )
    
    @function_tool
    async def lookup_fraud_case(self, context: RunContext, customer_name: str):
        """
        Look up pending fraud case for the customer by name.
        
        Args:
            customer_name: Full name of the customer
        """
        logger.info(f"Looking up fraud case for: {customer_name}")
        
        case = self.db.get_case_by_username(customer_name)
        
        if case:
            self.current_case = case
            self.call_stage = "verification"
            logger.info(f"Found case ID {case['id']} for {customer_name}")
            
            return f"Thank you, {customer_name}. I have your account information here. Before we proceed, I need to verify your identity for security purposes. {case['securityQuestion']}"
        else:
            self.call_stage = "not_found"
            return f"I apologize, but I don't have any pending fraud alerts for {customer_name}. This might be a system error. Please contact our customer service at 1800-XXX-XXXX. Have a great day!"
    
    @function_tool
    async def verify_customer(self, context: RunContext, security_answer: str):
        """
        Verify customer identity using their security question answer.
        
        Args:
            security_answer: Customer's answer to the security question
        """
        if not self.current_case:
            return "I need to look up your account first. What is your full name?"
        
        logger.info(f"Verifying customer for case ID {self.current_case['id']}")
        
        correct_answer = self.current_case['securityAnswer'].lower().strip()
        given_answer = security_answer.lower().strip()
        
        if correct_answer == given_answer:
            self.verified = True
            self.call_stage = "investigation"
            
            # Format transaction details
            case = self.current_case
            amount_formatted = f"₹{case['transactionAmount']:,.2f}"
            
            response = f"""Perfect, thank you for verifying. Now, let me share the details of the suspicious transaction we detected:

**Transaction Details:**
- Merchant: {case['transactionName']}
- Amount: {amount_formatted}
- Date & Time: {case['transactionTime']}
- Card ending in: {case['cardEnding']}
- Location: {case['transactionLocation']}
- Website: {case['transactionSource']}
- Category: {case['transactionCategory']}

This transaction occurred recently and was flagged by our fraud detection system due to unusual activity patterns.

**Important question:** Did you authorize this transaction of {amount_formatted} to {case['transactionName']}?"""
            
            return response
        else:
            self.call_stage = "verification_failed"
            logger.warning(f"Verification failed for case ID {self.current_case['id']}")
            
            # Update database
            self.db.update_case_status(
                case_id=self.current_case['id'],
                status='verification_failed',
                outcome='Customer failed security verification',
                verified=False
            )
            
            return "I'm sorry, but that answer doesn't match our records. For your security, I cannot proceed with this call. Please visit your nearest branch with a valid ID for assistance. Thank you."
    
    @function_tool
    async def resolve_case(self, context: RunContext, customer_authorized: bool):
        """
        Resolve the fraud case based on customer's confirmation.
        
        Args:
            customer_authorized: True if customer authorized the transaction, False if fraudulent
        """
        if not self.verified:
            return "I need to verify your identity first before we can proceed."
        
        if not self.current_case:
            return "No active fraud case found."
        
        case = self.current_case
        case_id = case['id']
        
        logger.info(f"Resolving case {case_id}: authorized={customer_authorized}")
        
        if customer_authorized:
            # Customer confirmed the transaction
            self.db.update_case_status(
                case_id=case_id,
                status='confirmed_safe',
                outcome=f"Customer {case['userName']} confirmed transaction to {case['transactionName']} as legitimate.",
                verified=True
            )
            
            response = f"""Thank you for confirming, {case['userName'].split()[0]}. 

I've updated our records to show this transaction to {case['transactionName']} was authorized by you. Your card will continue to work normally.

We apologize for any inconvenience. We take your account security very seriously, which is why we reach out when we detect unusual activity.

Is there anything else I can help you with today?"""
        
        else:
            # Fraudulent transaction
            self.db.update_case_status(
                case_id=case_id,
                status='confirmed_fraud',
                outcome=f"Customer {case['userName']} confirmed transaction to {case['transactionName']} as fraudulent. Card blocked and dispute initiated.",
                verified=True
            )
            
            amount = f"₹{case['transactionAmount']:,.2f}"
            response = f"""I understand, {case['userName'].split()[0]}. I'm very sorry this happened to you.

**Actions I'm taking immediately:**

1. ✅ **Blocking your card** ending in {case['cardEnding']} to prevent further unauthorized transactions
2. ✅ **Initiating a fraud dispute** for {amount} with {case['transactionName']}
3. ✅ **Issuing a new card** which will arrive at your registered address in 5-7 business days
4. ✅ **Monitoring your account** for any additional suspicious activity

**What happens next:**
- You will NOT be charged for this fraudulent transaction of {amount}
- Our fraud investigation team will contact {case['transactionSource']} to reverse the charge
- You'll receive an SMS confirmation with your reference number
- Your new card will have a different card number for security

**Important:** If you notice any other unauthorized transactions, please call us immediately at 1800-{self.bank_name.upper()}-FRAUD.

Your account security is our top priority. Is there anything else you'd like to ask about this case?"""
        
        self.call_stage = "resolution"
        return response
    
    @function_tool
    async def get_case_summary(self, context: RunContext):
        """Get summary of the current fraud case being investigated"""
        if not self.current_case:
            return "No active fraud case loaded."
        
        case = self.current_case
        return f"""
**Case Summary:**
- Customer: {case['userName']}
- Case ID: {case['id']}
- Status: {case['status']}
- Card: XXXX-{case['cardEnding']}
- Transaction: {case['transactionName']}
- Amount: ₹{case['transactionAmount']:,.2f}
- Verified: {self.verified}
- Stage: {self.call_stage}
"""

# ------------ Prewarm and Entrypoint ------------

def prewarm(proc: JobProcess):
    """Prewarm function to load models and initialize database"""
    proc.userdata["vad"] = silero.VAD.load()
    
    # Initialize fraud database
    fraud_db = FraudDatabase()
    proc.userdata["fraud_db"] = fraud_db
    
    # Log pending cases
    pending_cases = fraud_db.get_all_pending_cases()
    logger.info(f"🚨 Fraud Database initialized with {len(pending_cases)} pending cases")
    for case in pending_cases:
        logger.info(f"  - Case {case['id']}: {case['userName']} - ₹{case['transactionAmount']:,.2f} @ {case['transactionName']}")

async def entrypoint(ctx: JobContext):
    # Logging setup
    ctx.log_context_fields = {
        "room": ctx.room.name,
    }
    
    logger.info("🚨 Starting Fraud Alert Agent...")
    
    # Load fraud database from prewarm or create new
    if "fraud_db" in ctx.proc.userdata:
        fraud_db = ctx.proc.userdata["fraud_db"]
        logger.info("Using prewarmed fraud database")
    else:
        fraud_db = FraudDatabase()
        logger.info("Created new fraud database")

    # Voice agent session pipeline
    session = AgentSession(
        stt=deepgram.STT(model="nova-3"),
        llm=google.LLM(model="gemini-2.5-flash"),
        tts=murf.TTS(
            voice="Matthew",  # Professional, authoritative voice for bank security
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

    # Start session with Fraud Alert Agent
    logger.info("🎙️ Starting fraud alert agent session...")
    await session.start(
        agent=FraudAlertAgent(db=fraud_db, bank_name="SecureBank India"),
        room=ctx.room,
        room_input_options=RoomInputOptions(
            noise_cancellation=noise_cancellation.BVC(),
        ),
    )

    logger.info("🔗 Connecting to room...")
    await ctx.connect()
    logger.info("✅ Fraud Alert Agent connected successfully!")

if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint, prewarm_fnc=prewarm))
