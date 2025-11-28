# backend/src/agent.py
import logging
import os
import json
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

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
logger.setLevel(logging.INFO)

load_dotenv(".env.local")

# ---------- Paths ----------
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(file)))
SHARED_DIR = os.path.join(BASE_DIR, "shared-data")
os.makedirs(SHARED_DIR, exist_ok=True)
CASE_PATH = os.path.join(SHARED_DIR, "fraud_cases.json")

# ---------- Simple JSON DB helpers ----------
def ensure_cases_file():
    if not os.path.exists(CASE_PATH):
        sample = [
            {
                "userName": "john",
                "securityIdentifier": "ABC123",
                "cardEnding": "4242",
                "case": "pending_review",
                "transactionName": "ABC Industry",
                "transactionAmount": "₹2,450.00",
                "transactionTime": "2025-11-20T14:12:00+05:30",
                "transactionCategory": "e-commerce",
                "transactionSource": "alibaba.com",
                "location": "Delhi, India",
                "security_question": "What is my favorite pet?",
                "security_answer": "dog",
                "outcome": "",
                "last_updated": ""
            }
        ]
        with open(CASE_PATH, "w", encoding="utf-8") as f:
            json.dump(sample, f, indent=2, ensure_ascii=False)

def load_cases() -> List[Dict[str, Any]]:
    ensure_cases_file()
    with open(CASE_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def save_cases(cases: List[Dict[str, Any]]):
    with open(CASE_PATH, "w", encoding="utf-8") as f:
        json.dump(cases, f, indent=2, ensure_ascii=False)

def find_case_by_username(username: str) -> Optional[Dict[str, Any]]:
    username_normal = username.strip().lower()
    cases = load_cases()
    for c in cases:
        if c.get("userName", "").strip().lower() == username_normal:
            return c
    return None

def update_case_in_db(updated_case: Dict[str, Any]):
    cases = load_cases()
    changed = False
    for idx, c in enumerate(cases):
        if c.get("userName", "").strip().lower() == updated_case.get("userName", "").strip().lower():
            cases[idx] = updated_case
            changed = True
            break
    if not changed:
        cases.append(updated_case)
    save_cases(cases)

# ---------- Murf TTS voice (calm professional) ----------
TTS_FRAUD = murf.TTS(
    voice="en-US-matthew",  # change to your Murf voice id if needed
    style="Conversation",
    tokenizer=tokenize.basic.SentenceTokenizer(min_sentence_len=2),
    text_pacing=True,
)

# ---------- Tools exposed to model ----------
@function_tool
async def get_case_by_username(ctx: RunContext, username: str) -> Dict[str, Any]:
    c = find_case_by_username(username)
    if not c:
        return {"error": f"No fraud case found for username '{username}'."}
    # safe projection (no sensitive fields)
    return {
        "userName": c.get("userName"),
        "securityIdentifier": c.get("securityIdentifier"),
        "cardEnding": c.get("cardEnding"),
        "transactionName": c.get("transactionName"),
        "transactionAmount": c.get("transactionAmount"),
        "transactionTime": c.get("transactionTime"),
        "location": c.get("location"),
        "transactionSource": c.get("transactionSource"),
        "transactionCategory": c.get("transactionCategory"),
        "security_question": c.get("security_question"),
        "case": c.get("case")
    }

@function_tool
async def verify_answer(ctx: RunContext, username: str, answer: str) -> Dict[str, Any]:
    c = find_case_by_username(username)
    if not c:
        return {"error": "case_not_found"}
    correct = str(c.get("security_answer", "")).strip().lower()
    given = str(answer).strip().lower()
    ok = (given == correct)
    return {"verified": ok, "case": {"userName": c.get("userName"), "case": c.get("case")}}

@function_tool
async def mark_case(ctx: RunContext, username: str, outcome: str, note: str) -> Dict[str, Any]:
    c = find_case_by_username(username)
    if not c:
        return {"error": "case_not_found"}
    c["case"] = outcome
    c["outcome"] = note
    c["last_updated"] = datetime.now(timezone.utc).isoformat()
    update_case_in_db(c)
    return {"result": "ok", "case": c}

# ---------- Agents ----------
class FraudRouterAgent(Agent):
    def init(self, **kwargs):
        instructions = """
You are a calm professional fraud-detection representative for a fictional bank.
Ask the user for their username (non-sensitive). When you receive the username reply,
the system has a tool get_case_by_username available; call it to load the case.
If no case found, ask the user to re-check the username.
If case found, ask the stored security question (from the tool response) to verify identity.
"""
        super().init(instructions=instructions, tts=TTS_FRAUD, **kwargs)

    async def on_enter(self) -> None:
        await self.session.generate_reply(instructions=(
            "Hello, this is the Fraud Department at Example Bank. We are calling about a suspicious transaction on your account. "
            "To look up your case I need your username. Please say your username now."
        ))


class FraudCaseAgent(Agent):
    def init(self, **kwargs):
        instructions = """
You are a calm fraud representative. Use tools:
- get_case_by_username(username)
- verify_answer(username, answer)
- mark_case(username, outcome, note)

Flow:
1) Confirm username and call get_case_by_username to load the case.
2) Ask the stored security question exactly as returned by the tool.
3) Call verify_answer with the user's response.
4) If verification fails: call mark_case(username, "verification_failed", "...") and say you cannot proceed.
5) If verification succeeds: read transaction details and ask the user "Did you make this transaction?"
6) If user says yes: call mark_case(username, "confirmed_safe", "...") and confirm.
7) If user says no: call mark_case(username, "confirmed_fraud", "...") and explain mock actions.
"""
        super().init(instructions=instructions, tts=TTS_FRAUD, **kwargs)

    async def on_enter(self) -> None:
        await self.session.generate_reply(instructions=(
            "Please confirm your username so I can load the suspicious transaction."
        ))

# ---------- Prewarm ----------
def prewarm(proc: JobProcess):
    proc.userdata["vad"] = silero.VAD.load()

# ---------- Entrypoint ----------
async def entrypoint(ctx: JobContext):
    ctx.log_context_fields = {"room": ctx.room.name}

    # create session WITHOUT default tts so individual agents' TTS are used
    session = AgentSession(
        stt=deepgram.STT(model="nova-3"),
        llm=google.LLM(model="gemini-2.5-flash"),
        turn_detection=MultilingualModel(),
        vad=ctx.proc.userdata["vad"],
        preemptive_generation=True,
        tools=[get_case_by_username, verify_answer, mark_case],
    )

    session.userdata = {}

    usage_collector = metrics.UsageCollector()

    @session.on("metrics_collected")
    def _on_metrics_collected(ev: MetricsCollectedEvent):
        metrics.log_metrics(ev.metrics)
        usage_collector.collect(ev.metrics)

    async def log_usage():
        logger.info("Usage summary: %s", usage_collector.get_summary())

    ctx.add_shutdown_callback(log_usage)

    await session.start(agent=FraudRouterAgent(), room=ctx.room, room_input_options=RoomInputOptions(noise_cancellation=noise_cancellation.BVC()))
    await ctx.connect()

if name == "main":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint, prewarm_fnc=prewarm))
