import logging
import os
import asyncio
import random
import re
from datetime import datetime
from typing import Annotated, Optional
from dataclasses import dataclass

logger = logging.getLogger("agent")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

logger.info("========== FRAUD ALERT AGENT LOADED ==========")

from dotenv import load_dotenv
from pydantic import Field
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
    RunContext,
    function_tool,
)
from livekit.plugins import murf, silero, google, deepgram, noise_cancellation
from livekit.plugins.turn_detector.multilingual import MultilingualModel

from database import FraudDatabase, FraudCase as DBFraudCase

load_dotenv(".env.local")

# ============================
# INIT DB
# ============================
db = FraudDatabase()


# ============================
# DIGIT WORD PARSING
# ============================
DIGIT_WORDS = {
    "zero": "0", "oh": "0",
    "one": "1", "won": "1",
    "two": "2", "to": "2", "too": "2",
    "three": "3",
    "four": "4", "for": "4",
    "five": "5",
    "six": "6",
    "seven": "7",
    "eight": "8", "ate": "8",
    "nine": "9",
}


def convert_spoken_digits_to_numbers(text: str) -> str:
    """
    Converts spoken digit words to actual digits.
    e.g., "seven three two one" → "7321"
    Accepts mixed text like "It's seven three two one."
    """
    text = text.lower()
    # Remove punctuation
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    tokens = text.split()

    digits = []
    for t in tokens:
        if t.isdigit():
            digits.append(t)
        elif t in DIGIT_WORDS:
            digits.append(DIGIT_WORDS[t])

    out = "".join(digits)
    # Only keep last 4 digits if too long
    if len(out) > 4:
        out = out[-4:]

    return out


# ============================
# FRAUD CASE MODELS
# ============================
@dataclass
class FraudCase:
    id: str
    userName: str
    securityIdentifier: str
    cardEnding: str
    cardType: str
    transactionName: str
    transactionAmount: str
    transactionTime: str
    transactionLocation: str
    transactionCategory: str
    transactionSource: str
    status: str
    securityQuestion: str
    securityAnswer: str
    createdAt: str
    outcome: Optional[str] = None
    outcomeNote: Optional[str] = None


@dataclass
class SessionData:
    fraud_case: Optional[FraudCase] = None
    user_verified: bool = False
    call_phase: str = "initial"


# ============================
# SAVE CASE
# ============================
def save_fraud_case(fraud_case: FraudCase) -> bool:
    try:
        success = db.update_fraud_case_status(
            fraud_case.id,
            fraud_case.status,
            fraud_case.outcome or "pending",
            fraud_case.outcomeNote or ""
        )
        return success
    except Exception as e:
        logger.error("Error saving fraud case: %s", e)
        return False


# ============================
# TOOL 1 — VERIFY CARD
# ============================
@function_tool
async def verify_customer_card(
    ctx: RunContext[SessionData],
    card_ending_digits: Annotated[str, Field(description="Last 4 digits of customer's card")],
) -> str:

    # Convert spoken digits → numbers
    extracted = convert_spoken_digits_to_numbers(card_ending_digits)
    logger.info("[CARD INPUT] Raw='%s' → Clean='%s'", card_ending_digits, extracted)

    if extracted == "":
        return (
            "I couldn't detect any digits. Please repeat only the last four digits of your card number."
        )

    all_cases = db.get_all_fraud_cases()
    matches = []

    for case in all_cases:
        stored = re.sub(r"\D", "", case.cardEnding or "")
        if len(stored) >= 4 and stored[-4:] == extracted:
            matches.append(case)

    if not matches:
        return (
            "I'm sorry, I cannot find an account matching those card digits. "
            "For security reasons, I cannot proceed with this call."
        )

    selected = None
    for m in matches:
        if m.status.lower() == "pending":
            selected = m
            break
    if not selected:
        selected = matches[0]

    fraud_case = FraudCase(
        id=selected.id,
        userName=selected.userName,
        securityIdentifier=selected.securityIdentifier,
        cardEnding=selected.cardEnding,
        cardType=selected.cardType,
        transactionName=selected.transactionName,
        transactionAmount=selected.transactionAmount,
        transactionTime=selected.transactionTime,
        transactionLocation=selected.transactionLocation,
        transactionCategory=selected.transactionCategory,
        transactionSource=selected.transactionSource,
        status=selected.status,
        securityQuestion=selected.securityQuestion,
        securityAnswer=selected.securityAnswer,
        createdAt=selected.createdAt,
        outcome=selected.outcome,
        outcomeNote=selected.outcomeNote,
    )

    ctx.userdata.fraud_case = fraud_case

    return (
        f"Great! I found your account for {selected.userName}. "
        f"To complete verification, please answer this security question: "
        f"{selected.securityQuestion}"
    )


# ============================
# TOOL 2 — VERIFY SECURITY
# ============================
@function_tool
async def verify_customer_security(
    ctx: RunContext[SessionData],
    security_answer: Annotated[str, Field(description="Security answer")],
) -> str:

    if ctx.userdata.fraud_case is None:
        return "We haven't verified your card yet. Please provide your card digits first."

    fraud_case = ctx.userdata.fraud_case

    provided = (security_answer or "").strip().lower()
    expected = (fraud_case.securityAnswer or "").strip().lower()

    if provided == expected and provided != "":
        ctx.userdata.user_verified = True
        return (
            f"Thank you. Your identity is verified. "
            f"Let me read the suspicious transaction on your {fraud_case.cardType} card "
            f"ending in {fraud_case.cardEnding}."
        )

    # Security failed
    fraud_case.status = "verification_failed"
    fraud_case.outcome = "verification_failed"
    fraud_case.outcomeNote = f"Failed security check at {datetime.now().isoformat()}"
    save_fraud_case(fraud_case)

    return (
        "That answer is incorrect. For security reasons, I cannot proceed. "
        "This call will now be ended."
    )


# ============================
# TOOL 3 — DETAILS
# ============================
@function_tool
async def get_current_fraud_case_details(ctx: RunContext[SessionData]) -> str:
    if ctx.userdata.fraud_case is None:
        return "No active fraud case."

    c = ctx.userdata.fraud_case
    return (
        f"Customer: {c.userName}. Transaction of {c.transactionAmount} at {c.transactionName}, "
        f"on {c.transactionTime} in {c.transactionLocation}."
    )


# ============================
# TOOL 4 — CONFIRM SAFE
# ============================
@function_tool
async def confirm_transaction_legitimate(ctx: RunContext[SessionData]) -> str:
    if ctx.userdata.fraud_case is None:
        return "No active fraud case."

    c = ctx.userdata.fraud_case

    c.status = "confirmed_safe"
    c.outcome = "legitimate"
    c.outcomeNote = (
        f"Customer confirmed as legitimate at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    )

    save_fraud_case(c)

    return (
        f"Thank you. I have marked the transaction of {c.transactionAmount} at "
        f"{c.transactionName} as legitimate. Your account remains secure."
    )


# ============================
# TOOL 5 — MARK FRAUD
# ============================
@function_tool
async def report_transaction_fraudulent(ctx: RunContext[SessionData]) -> str:
    if ctx.userdata.fraud_case is None:
        return "No active fraud case."

    c = ctx.userdata.fraud_case

    c.status = "confirmed_fraud"
    c.outcome = "fraudulent"
    c.outcomeNote = (
        f"Customer confirmed fraud at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    )

    save_fraud_case(c)

    return (
        f"I understand. I have flagged this transaction as fraudulent. "
        f"The card ending in {c.cardEnding} has been blocked, and a dispute has been initiated. "
        f"A representative will follow up with you soon."
    )


# ============================
# AGENT CLASS
# ============================
class FraudDetectionAgent(Agent):
    def __init__(self):
        instructions = """
        You are a professional fraud detection specialist for SecureBank.

        Rules:
        - Never ask for full card numbers or PIN.
        - Only ask for the last 4 digits.
        - Use verification tools for card + security question.
        - After verification, explain the suspicious transaction.
        - Ask if the user made it.
        - Then call the correct tool to mark safe or fraudulent.
        - Keep responses short, clear, calm, and professional.
        """

        super().__init__(
            instructions=instructions,
            tools=[
                verify_customer_card,
                verify_customer_security,
                get_current_fraud_case_details,
                confirm_transaction_legitimate,
                report_transaction_fraudulent,
            ],
        )


# ============================
# PREWARM
# ============================
def prewarm(proc: JobProcess):
    proc.userdata["vad"] = silero.VAD.load()


# ============================
# MAIN ENTRYPOINT
# ============================
async def entrypoint(ctx: JobContext):
    session_data = SessionData()

    all_cases = db.get_all_fraud_cases()
    logger.info("Loaded %d fraud cases from DB.", len(all_cases))

    session = AgentSession(
        stt=deepgram.STT(model="nova-3"),
        llm=google.LLM(model="gemini-2.5-flash"),
        tts=murf.TTS(
            voice="en-IN-anusha",
            style="Conversation",
            tokenizer=tokenize.basic.SentenceTokenizer(min_sentence_len=2),
            text_pacing=True,
        ),
        turn_detection=MultilingualModel(),
        vad=ctx.proc.userdata["vad"],
        userdata=session_data,
    )

    usage_collector = metrics.UsageCollector()

    @session.on("metrics_collected")
    def _on_metrics(ev: MetricsCollectedEvent):
        metrics.log_metrics(ev.metrics)
        usage_collector.collect(ev.metrics)

    async def log_usage():
        logger.info("Usage Summary: %s", usage_collector.get_summary())

    ctx.add_shutdown_callback(log_usage)

    await session.start(
        agent=FraudDetectionAgent(),
        room=ctx.room,
        room_input_options=RoomInputOptions(
            noise_cancellation=noise_cancellation.BVC()
        ),
    )

    await ctx.connect()


if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint, prewarm_fnc=prewarm))
