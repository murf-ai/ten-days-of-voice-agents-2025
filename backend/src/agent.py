# ===========================================
# Fraud Alert Voice Agent (LiveKit) - Day 6
# ===========================================

import json
import logging
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

from livekit.agents import (
    Agent,
    AgentSession,
    JobContext,
    JobProcess,
    RoomInputOptions,
    WorkerOptions,
    cli,
)

from livekit.plugins import (
    deepgram,
    google,
    murf,
    noise_cancellation,
    silero,
)
from livekit.plugins.turn_detector.multilingual import MultilingualModel


# ------------------------------------------
# Logging + ENV
# ------------------------------------------
logger = logging.getLogger("fraud_agent")
load_dotenv(".env.local")


# ------------------------------------------
# Fake Fraud Case "Database"
# ------------------------------------------
DB_PATH = Path("shared-data/fraud_case.json")
DB_PATH.parent.mkdir(exist_ok=True, parents=True)

SAMPLE_FRAUD_CASE = {
    "userName": "John",
    "securityIdentifier": "12345",
    "securityQuestion": "What is your favorite color?",
    "securityAnswer": "blue",
    "cardEnding": "4242",
    "transactionName": "ABC Electronics",
    "transactionAmount": "₹12,499",
    "transactionTime": "2024-10-12 14:30",
    "transactionLocation": "Mumbai",
    "transactionCategory": "e-commerce",
    "transactionSource": "abc-electronics.com",
    "status": "pending_review",
    "note": ""
}

# create database if missing
if not DB_PATH.exists():
    with open(DB_PATH, "w") as f:
        json.dump(SAMPLE_FRAUD_CASE, f, indent=2)


def load_case():
    return json.load(open(DB_PATH, "r"))


def save_case(data):
    with open(DB_PATH, "w") as f:
        json.dump(data, f, indent=2)


# ------------------------------------------
# Fraud Alert Agent Class
# ------------------------------------------
class FraudAlertAgent(Agent):

    def __init__(self):
        super().__init__(
            instructions=(
                "You are a Fraud Alert Representative from a fictional bank named SecureBank. "
                "You must follow the fraud alert flow strictly and avoid all sensitive requests. "
                "Only use the fake data in the database. "
                "Never ask for PIN, OTP, full card number, CVV, or passwords."
            )
        )
        self.sessions = {}

    # ------------------ When call begins ------------------
    async def on_join(self, ctx):
        sid = ctx.session.session_id
        self.sessions[sid] = {
            "stage": "ask_username",
            "verified": False,
            "case": None,
        }

        await ctx.send_speech(
            "Hello, this is the SecureBank Fraud Detection Department. "
            "We detected a potentially suspicious transaction. "
            "To assist you, may I have your username?"
        )

    # ------------------ When user speaks ------------------
    async def on_user_message(self, message, ctx):
        sid = ctx.session.session_id
        state = self.sessions[sid]
        msg = (message.text or "").strip().lower()

        # end flow
        if msg in ["bye", "exit", "stop"]:
            return await self.finish(ctx, state)

        # Stages
        if state["stage"] == "ask_username":
            return await self.handle_username(msg, ctx, state)

        if state["stage"] == "security_question":
            return await self.handle_verification(msg, ctx, state)

        if state["stage"] == "confirm_transaction":
            return await self.handle_transaction_confirmation(msg, ctx, state)

    # ------------------ Username Handling ------------------
    async def handle_username(self, msg, ctx, state):
        fraud_case = load_case()

        if msg != fraud_case["userName"].lower():
            await ctx.send_speech(
                "I'm sorry, that username does not match our records. "
                "Please say your username again."
            )
            return

        # Username matched
        state["case"] = fraud_case
        state["stage"] = "security_question"

        await ctx.send_speech(
            f"Thank you. For security, please answer this question: "
            f"{fraud_case['securityQuestion']}"
        )

    # ------------------ Verification ------------------
    async def handle_verification(self, msg, ctx, state):
        fraud_case = state["case"]

        if msg.strip() != fraud_case["securityAnswer"].lower():
            fraud_case["status"] = "verification_failed"
            fraud_case["note"] = "User failed verification."
            save_case(fraud_case)

            await ctx.send_speech(
                "I'm sorry, the answer does not match our records. "
                "For your security, we cannot proceed further. Goodbye."
            )
            return await self.finish(ctx, state)

        # Verification successful
        state["verified"] = True
        state["stage"] = "confirm_transaction"

        await ctx.send_speech(
            "Thank you, verification successful. "
            "Here are the details of the suspicious transaction:"
        )
        await ctx.send_speech(
            f"Merchant: {fraud_case['transactionName']}. "
            f"Amount: {fraud_case['transactionAmount']}. "
            f"Location: {fraud_case['transactionLocation']}. "
            f"Time: {fraud_case['transactionTime']}. "
            f"Card ending with {fraud_case['cardEnding']}. "
            "Did you make this transaction? Please say yes or no."
        )

    # ------------------ Transaction Confirmation ------------------
    async def handle_transaction_confirmation(self, msg, ctx, state):
        fraud_case = state["case"]

        if "yes" in msg:
            fraud_case["status"] = "confirmed_safe"
            fraud_case["note"] = "Customer confirmed transaction as legitimate."
            save_case(fraud_case)

            await ctx.send_speech(
                "Thank you. We have marked this transaction as safe."
            )
            return await self.finish(ctx, state)

        if "no" in msg:
            fraud_case["status"] = "confirmed_fraud"
            fraud_case["note"] = "Customer denied the transaction. Card blocked."
            save_case(fraud_case)

            await ctx.send_speech(
                "Thank you. We have blocked your card and initiated a dispute. "
                "A fraud specialist will contact you shortly."
            )
            return await self.finish(ctx, state)

        await ctx.send_speech(
            "I didn't understand that. Please say yes or no."
        )

    # ------------------ End Call ------------------
    async def finish(self, ctx, state):
        await ctx.send_speech(
            "Thank you for your time. SecureBank cares about your safety. Goodbye."
        )


# ------------------------------------------
# Prewarm VAD
# ------------------------------------------
vad_model = silero.VAD.load()


def prewarm(proc: JobProcess):
    proc.userdata["vad"] = vad_model


# ------------------------------------------
# Entrypoint (Same as your SDR version)
# ------------------------------------------
async def entrypoint(ctx: JobContext):
    session = AgentSession(
        stt=deepgram.STT(model="nova-3"),
        llm=google.LLM(model="gemini-2.5-flash"),
        tts=murf.TTS(voice="en-US-matthew", style="Conversation"),
        turn_detection=MultilingualModel(),
        vad=ctx.proc.userdata["vad"],
        preemptive_generation=True,
    )

    await session.start(
        agent=FraudAlertAgent(),
        room=ctx.room,
        room_input_options=RoomInputOptions(
            noise_cancellation=noise_cancellation.BVC()
        ),
    )
    await ctx.connect()


if __name__ == "__main__":
    cli.run_app(
        WorkerOptions(
            entrypoint_fnc=entrypoint,
            prewarm_fnc=prewarm,
        )
    )
