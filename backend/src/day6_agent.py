import logging
import json
import os
from typing import Annotated
from dotenv import load_dotenv

from livekit.agents import (
    Agent,
    AgentSession,
    JobContext,
    JobProcess,
    RoomInputOptions,
    WorkerOptions,
    cli,
    llm,
    metrics,
    tokenize,
)
from livekit.plugins import murf, deepgram, google, silero, noise_cancellation
from livekit.plugins.turn_detector.multilingual import MultilingualModel

load_dotenv(".env.local")
logger = logging.getLogger("fraud-agent")

DB_PATH = os.path.join(os.path.dirname(__file__), "fraud_db.json")

class FraudDatabase:
    def __init__(self, path):
        self.path = path

    def get_case(self, username):
        try:
            with open(self.path, "r") as f:
                data = json.load(f)
                for case in data:
                    if case["userName"].lower() == username.lower():
                        return case
        except Exception as e:
            logger.error(f"Error reading DB: {e}")
        return None

    def update_case(self, username, status, outcome):
        try:
            with open(self.path, "r") as f:
                data = json.load(f)
            
            updated = False
            for case in data:
                if case["userName"].lower() == username.lower():
                    case["status"] = status
                    case["outcome"] = outcome
                    updated = True
                    break
            
            if updated:
                with open(self.path, "w") as f:
                    json.dump(data, f, indent=2)
                return True
        except Exception as e:
            logger.error(f"Error writing DB: {e}")
        return False

class FraudAgent(Agent):
    def __init__(self, case, db):
        super().__init__()
        self.case = case
        self.db = db
        self.instructions = f"""
        You are a Fraud Detection Representative for Bank of LiveKit.
        Your goal is to verify a suspicious transaction with the customer, {case['userName']}.
        
        Case Details:
        - Merchant: {case['transactionName']}
        - Amount: {case['transactionAmount']}
        - Time: {case['transactionTime']}
        - Location: {case['transactionLocation']}
        - Card Ending: {case['cardEnding']}
        
        Security Question: {case['securityQuestion']}
        Expected Answer: {case['securityAnswer']}

        Protocol:
        1. Introduce yourself and the bank. State you are calling about a suspicious transaction.
        2. Ask the security question to verify identity. DO NOT proceed until verified.
           - Use the `verify_identity` tool to check the answer.
        3. If verified, read out the transaction details clearly.
        4. Ask if they authorized this transaction.
        5. If YES (Safe):
           - Mark case as 'confirmed_safe' using `submit_report`.
           - Thank them and end the call.
        6. If NO (Fraud):
           - Mark case as 'confirmed_fraud' using `submit_report`.
           - Inform them the card is blocked and a new one is on the way. End the call.
        
        Be professional, calm, and reassuring.
        """

    @llm.ai_callable(description="Verify the user's identity by checking their security answer")
    def verify_identity(self, 
                        user_answer: Annotated[str, llm.TypeInfo(description="The answer provided by the user")]):
        """
        Check if the user's answer matches the expected security answer.
        """
        expected = self.case['securityAnswer'].lower()
        if user_answer.lower() == expected:
            return "Verification Successful. Proceed with transaction details."
        else:
            return "Verification Failed. Ask the user to try again or end the call if repeated failures."

    @llm.ai_callable(description="Submit the final status of the fraud case")
    def submit_report(self, 
                      status: Annotated[str, llm.TypeInfo(description="Final status: 'confirmed_safe' or 'confirmed_fraud'")],
                      notes: Annotated[str, llm.TypeInfo(description="Brief outcome notes")]):
        """
        Update the fraud case in the database with the final status and notes.
        """
        success = self.db.update_case(self.case['userName'], status, notes)
        if success:
            return "Case updated successfully."
        else:
            return "Failed to update case."

def prewarm(proc: JobProcess):
    proc.userdata["vad"] = silero.VAD.load()

async def entrypoint(ctx: JobContext):
    ctx.log_context_fields = {"room": ctx.room.name}
    
    # Initialize DB and load case
    db = FraudDatabase(DB_PATH)
    # For MVP, we hardcode looking for "John" or pick the first one
    # In a real scenario, we might get username from job metadata or room name
    case = db.get_case("John")
    
    if not case:
        logger.error("No case found for John")
        return

    logger.info(f"Loaded case for {case['userName']}")

    agent = FraudAgent(case, db)

    session = AgentSession(
        stt=deepgram.STT(model="nova-3"),
        llm=google.LLM(model="gemini-2.5-flash"),
        tts=murf.TTS(
            voice="en-US-matthew", 
            style="Conversation",
            tokenizer=tokenize.basic.SentenceTokenizer(min_sentence_len=2),
            text_pacing=True
        ),
        turn_detection=MultilingualModel(),
        vad=ctx.proc.userdata["vad"],
        preemptive_generation=True,
    )

    await session.start(
        agent=agent,
        room=ctx.room,
        room_input_options=RoomInputOptions(
            noise_cancellation=noise_cancellation.BVC(),
        ),
    )

    await ctx.connect()
    
    # Trigger the agent to speak first
    await agent.say("Hello? Is this John?", allow_interruptions=True)

if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint, prewarm_fnc=prewarm))
