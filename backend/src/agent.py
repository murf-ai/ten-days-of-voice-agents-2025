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
    metrics,
    tokenize,
    function_tool,
    RunContext,
)
from livekit.plugins import murf, deepgram, google, silero, noise_cancellation
from livekit.plugins.turn_detector.multilingual import MultilingualModel

load_dotenv(".env.local")
logger = logging.getLogger("fraud-agent")

DB_PATH = os.path.join(os.path.dirname(__file__), "fraud_db.json")

# -------------------------
# DATABASE
# -------------------------

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

# -------------------------
# AGENT
# -------------------------

class FraudAgent(Agent):
    def __init__(self, case, db):

        instructions = f"""
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
        1. Introduce yourself and ask the security question.
        2. Use the `verify_identity` tool for checking the answer.
        3. If verified: read the details & ask if they authorized it.
        4. If YES → use submit_report('confirmed_safe').
        5. If NO → use submit_report('confirmed_fraud').
        """

        super().__init__(instructions=instructions)

        self.case = case
        self.db = db

    # -------------------------
    # TOOL 1 — VERIFY IDENTITY
    # -------------------------
    @function_tool
    async def verify_identity(self, ctx: RunContext, user_answer: str):
        """Verify the user's identity by checking their security answer."""
        expected = self.case['securityAnswer'].lower()

        if user_answer.lower() == expected:
            return "Verification Successful. Proceed."
        else:
            return "Verification Failed. Ask again."

    # -------------------------
    # TOOL 2 — SUBMIT REPORT
    # -------------------------
    @function_tool
    async def submit_report(self, ctx: RunContext, status: str, notes: str):
        """Submit the final fraud case result."""
        success = self.db.update_case(self.case['userName'], status, notes)

        if success:
            return "Case updated successfully."
        return "Failed to update case."


# -------------------------
# PREWARM
# -------------------------

def prewarm(proc: JobProcess):
    proc.userdata["vad"] = silero.VAD.load()


# -------------------------
# ENTRYPOINT
# -------------------------

async def entrypoint(ctx: JobContext):

    ctx.log_context_fields = {"room": ctx.room.name}

    db = FraudDatabase(DB_PATH)
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
            text_pacing=True,
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

    # Correct way to make agent talk
    await session.agent_say(
        "Hello, this is the Fraud Team from Bank of LiveKit. Is this John?"
    )


# -------------------------
# MAIN
# -------------------------

if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint, prewarm_fnc=prewarm))
