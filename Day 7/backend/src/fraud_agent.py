import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from livekit.agents import (
    Agent,
    AgentSession,
    JobContext,
    JobProcess,
    MetricsCollectedEvent,
    RoomInputOptions,
    RunContext,
    WorkerOptions,
    cli,
    function_tool,
    metrics,
    tokenize,
)
from livekit.plugins import (
    murf,
    silero,
    google,
    deepgram,
    noise_cancellation,
)
from livekit.plugins.turn_detector.multilingual import MultilingualModel

logger = logging.getLogger("fraud_agent")

load_dotenv(".env.local")

FRAUD_DB_PATH = Path("fraud_cases.json")


def load_fraud_cases() -> list:
    if not FRAUD_DB_PATH.exists():
        return []
    try:
        with open(FRAUD_DB_PATH, "r") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error loading fraud cases: {e}")
        return []


def save_fraud_cases(cases: list) -> None:
    try:
        with open(FRAUD_DB_PATH, "w") as f:
            json.dump(cases, f, indent=2)
    except Exception as e:
        logger.error(f"Error saving fraud cases: {e}")


def get_case_by_username(username: str) -> Optional[dict]:
    cases = load_fraud_cases()
    for c in cases:
        if c.get("userName", "").lower() == username.lower():
            return c
    return None


class FraudAgent(Agent):
    def __init__(self) -> None:
        super().__init__(
            instructions=(
                "You are a fraud detection representative for a fictional bank. Use calm, professional, "
                "and reassuring language. Introduce yourself as the bank's fraud department, verify the user using a non-sensitive security ",
                "question, read out the suspicious transaction, then ask if they made it. Do not ask for full card numbers, PINs, passwords, or any sensitive info. "
                "If verified, update case status to confirmed_safe or confirmed_fraud based on the user's answer. If verification fails, inform the user you cannot continue and exit."
            )
        )
        self.room = None
        self.case = None

    @function_tool
    async def greet(self, context: RunContext) -> str:
        """Introduce the agent as the bank fraud department and start the call."""
        return (
            "Hello, this is the Bank Fraud Department. I'm calling about a suspicious transaction that may be on your account. Can I confirm your name?"
        )

    @function_tool
    async def ask_for_username(self, context: RunContext, username: str) -> str:
        logger.info(f"ask_for_username: {username}")
        c = get_case_by_username(username)
        if not c:
            return f"I couldn't find any open fraud cases for {username}. Are you sure the name is correct?"
        self.case = c
        return f"Thanks {username}. I've found a case. I'll ask one short security question to verify your identity. {c.get('securityQuestion', '')}"

    @function_tool
    async def verify_security_answer(self, context: RunContext, answer: str) -> str:
        if not self.case:
            return "I don't have an active case to verify."
        expected = self.case.get("securityAnswer", "").strip().lower()
        if answer.strip().lower() == expected:
            return "Verification successful. I'll read the suspicious transaction now."
        else:
            self.case["case"] = "verification_failed"
            self.case["last_updated"] = datetime.now().isoformat()
            self.case["outcome_note"] = "Verification failed during call."
            # Persist
            cases = load_fraud_cases()
            for i, val in enumerate(cases):
                if val.get("securityIdentifier") == self.case.get("securityIdentifier"):
                    cases[i] = self.case
            save_fraud_cases(cases)
            return "I'm sorry, I couldn't verify your identity. For your safety, I cannot discuss this case further. Goodbye."

    @function_tool
    async def read_transaction(self, context: RunContext) -> str:
        if not self.case:
            return "No transaction loaded."
        masked = f"**** {self.case.get('cardEnding', 'XXXX')}"
        return (
            f"We detected a suspicious transaction on your card {masked}, amount {self.case.get('amount')}, "
            f"merchant {self.case.get('transactionName')}, from {self.case.get('transactionSource')} located in {self.case.get('location')} at {self.case.get('transactionTime')}. "
            "Did you make this transaction?"
        )

    @function_tool
    async def mark_safe(self, context: RunContext) -> str:
        if not self.case:
            return "No case to mark."
        self.case["case"] = "confirmed_safe"
        self.case["last_updated"] = datetime.now().isoformat()
        self.case["outcome_note"] = "Customer confirmed transaction as legitimate."
        cases = load_fraud_cases()
        for i, val in enumerate(cases):
            if val.get("securityIdentifier") == self.case.get("securityIdentifier"):
                cases[i] = self.case
        save_fraud_cases(cases)
        return "Thanks for confirming. We've marked the case as safe. If you notice anything else, contact the bank. Goodbye."

    @function_tool
    async def mark_fraudulent(self, context: RunContext) -> str:
        if not self.case:
            return "No case to mark."
        self.case["case"] = "confirmed_fraud"
        self.case["last_updated"] = datetime.now().isoformat()
        self.case["outcome_note"] = "Customer denied the transaction; mock card blocked and dispute raised."
        cases = load_fraud_cases()
        for i, val in enumerate(cases):
            if val.get("securityIdentifier") == self.case.get("securityIdentifier"):
                cases[i] = self.case
        save_fraud_cases(cases)
        return (
            "Thank you. We've marked this transaction as fraudulent, blocked the card, and raised a dispute. "
            "Our fraud team will reach out soon. Goodbye."
        )


def prewarm(proc: JobProcess):
    proc.userdata["vad"] = silero.VAD.load()


async def entrypoint(ctx: JobContext):
    # Logging setup
    ctx.log_context_fields = {
        "room": ctx.room.name,
    }

    session = AgentSession(
        stt=deepgram.STT(model="nova-3"),
        llm=google.LLM(model="gemini-2.5-flash"),
        tts=murf.TTS(voice="en-US-matthew", style="Conversation", tokenizer=tokenize.basic.SentenceTokenizer(min_sentence_len=2), text_pacing=True),
        turn_detection=MultilingualModel(),
        vad=ctx.proc.userdata["vad"],
        preemptive_generation=True,
    )

    usage_collector = metrics.UsageCollector()

    @session.on("metrics_collected")
    def _on_metrics_collected(ev: MetricsCollectedEvent):
        metrics.log_metrics(ev.metrics)
        usage_collector.collect(ev.metrics)

    async def log_usage():
        summary = usage_collector.get_summary()
        logger.info(f"Usage: {summary}")

    ctx.add_shutdown_callback(log_usage)

    agent = FraudAgent()
    agent.room = ctx.room

    await session.start(
        agent=agent,
        room=ctx.room,
        room_input_options=RoomInputOptions(noise_cancellation=noise_cancellation.BVC()),
    )

    await ctx.connect()


if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint, prewarm_fnc=prewarm))
