# backend/src/agent.py
import logging
import os
import json
import re
import uuid
import datetime
from typing import Dict, Any, List, Optional

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
    MetricsCollectedEvent,
)
from livekit.plugins import murf, silero, google, deepgram, noise_cancellation
from livekit.plugins.turn_detector.multilingual import MultilingualModel

logger = logging.getLogger("agent")
logger.setLevel(logging.INFO)

# Load env vars from .env.local
load_dotenv(".env.local")

# ------- Paths & constants -------
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "shared-data")
os.makedirs(DATA_DIR, exist_ok=True)

FAQ_FILE = os.path.join(DATA_DIR, "company_faq_lenskart.json")
LEADS_FILE = os.path.join(DATA_DIR, "leads_lenskart.json")

# Developer-uploaded screenshot (included in prompts / demo)
FILE_URL = "/mnt/data/Screenshot 2025-11-22 222905.png"

# ------- Ensure files exist & load FAQ -------
DEFAULT_FAQ = {
    "company": "Lenskart",
    "overview": "Lenskart is India's leading eyewear brand offering eyeglasses, sunglasses, contact lenses, and home eye check-ups.",
    "faq": [
        {"q": "What products do you offer?", "a": "We offer prescription eyeglasses, sunglasses, contact lenses, powered sunglasses, and accessories. We also provide home eye check-ups."},
        {"q": "Do you offer a free eye test?", "a": "Yes! Lenskart provides a free home eye test in multiple cities with certified optometrists."},
        {"q": "What is your pricing?", "a": "Eyeglasses start from ₹499, premium collections from ₹1500+, sunglasses from ₹599, and contact lenses from ₹199 onwards."},
        {"q": "Do you have a return or exchange policy?", "a": "Yes, Lenskart offers a 14-day no-questions-asked return or exchange policy on most products."},
        {"q": "How fast is delivery?", "a": "Standard eyeglasses are delivered within 3–7 days. Contact lenses and ready stock items ship faster."},
        {"q": "Do you have a free trial?", "a": "Yes! You can use the 3D Try-On on the app or website. Some frames also support Home Try-On."},
        {"q": "Who is Lenskart for?", "a": "Anyone who wants stylish, durable eyewear — students, professionals, seniors, or kids."}
    ]
}

def load_faq() -> Dict[str, Any]:
    if not os.path.exists(FAQ_FILE):
        with open(FAQ_FILE, "w", encoding="utf-8") as f:
            json.dump(DEFAULT_FAQ, f, indent=2, ensure_ascii=False)
        return DEFAULT_FAQ
    with open(FAQ_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

FAQ = load_faq()

def ensure_leads_file():
    if not os.path.exists(LEADS_FILE):
        with open(LEADS_FILE, "w", encoding="utf-8") as f:
            json.dump([], f, indent=2, ensure_ascii=False)

ensure_leads_file()

# ------- Simple keyword FAQ lookup -------
def _normalize(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip().lower())

def keyword_search_faq(query: str, top_n: int = 3) -> List[Dict[str, str]]:
    qnorm = _normalize(query)
    tokens = [t for t in re.split(r"\W+", qnorm) if t and len(t) > 2]
    matches = []
    overview = _normalize(FAQ.get("overview", ""))
    if any(tok in overview for tok in tokens):
        matches.append({"q": "About Lenskart", "a": FAQ.get("overview", "")})
    for item in FAQ.get("faq", []):
        cand = _normalize(item.get("q", "") + " " + item.get("a", ""))
        if any(tok in cand for tok in tokens):
            matches.append(item)
    # dedupe and limit
    seen = set()
    out = []
    for m in matches:
        key = m.get("q", "")
        if key not in seen:
            out.append(m)
            seen.add(key)
        if len(out) >= top_n:
            break
    if not out:
        out = FAQ.get("faq", [])[:top_n]
    return out

# ------- Validators -------
EMAIL_RE = re.compile(r"[^@]+@[^@]+\.[^@]+")
def is_valid_email(e: str) -> bool:
    return bool(EMAIL_RE.match((e or "").strip()))

# ------- Tools exposed to the LLM -------
@function_tool
async def find_faq(ctx: RunContext, question: str) -> Dict[str, Any]:
    """Return top-matching FAQ entries. MUST be used for product/company questions."""
    matches = keyword_search_faq(question)
    return {"matches": matches}

@function_tool
async def fill_lead_field(ctx: RunContext, field: str, value: str) -> Dict[str, Any]:
    """
    Deterministically fill one lead field in session.userdata['lead'].
    Use synonyms mapping; returns updated lead.
    """
    session = ctx.session
    ud = getattr(session, "userdata", {})
    lead = ud.get("lead", {"name": None, "email": None, "company": None, "role": None, "use_case": None, "team_size": None, "timeline": None})
    f = field.strip().lower()
    synonyms = {
        "name": "name", "fullname": "name",
        "email": "email", "e-mail": "email",
        "company": "company", "org": "company",
        "role": "role", "position": "role",
        "usecase": "use_case", "use case": "use_case", "use_case": "use_case",
        "team size": "team_size", "teamsize": "team_size", "team_size": "team_size",
        "timeline": "timeline", "when": "timeline"
    }
    f = synonyms.get(f, f)
    lead[f] = value.strip()
    ud["lead"] = lead
    asked = ud.get("asked", [])
    if f not in asked:
        asked.append(f)
        ud["asked"] = asked
    session.userdata = ud
    return {"lead": lead}

@function_tool
async def save_lead(ctx: RunContext, lead: Dict[str, Any]) -> Dict[str, str]:
    """Persist lead to JSON and return ID."""
    ensure_leads_file()
    with open(LEADS_FILE, "r", encoding="utf-8") as f:
        arr = json.load(f)
    entry = dict(lead)
    entry["_id"] = str(uuid.uuid4())[:8]
    entry["created_at"] = datetime.datetime.utcnow().isoformat() + "Z"
    arr.append(entry)
    with open(LEADS_FILE, "w", encoding="utf-8") as f:
        json.dump(arr, f, indent=2, ensure_ascii=False)
    return {"id": entry["_id"]}

@function_tool
async def get_lead_summary(ctx: RunContext, lead: Dict[str, Any]) -> str:
    """Return a compact spoken summary string for recap."""
    name = lead.get("name") or "(unknown)"
    email = lead.get("email") or "(unknown)"
    use_case = lead.get("use_case") or "(not provided)"
    team = lead.get("team_size") or "(unknown)"
    timeline = lead.get("timeline") or "(unspecified)"
    return f"{name} ({email}) is interested in {use_case}. Team size: {team}. Timeline: {timeline}."

@function_tool
async def ask_next_field(ctx: RunContext) -> Dict[str, Any]:
    """
    Server-side helper the LLM can call to get the next missing lead field and a suggested question.
    Returns: {field: str, question: str, required: bool}
    """
    session = ctx.session
    ud = getattr(session, "userdata", {})
    lead = ud.get("lead", {"name": None, "email": None, "company": None, "role": None, "use_case": None, "team_size": None, "timeline": None})
    order = ["name", "email", "company", "role", "use_case", "team_size", "timeline"]
    labels = {
        "name": "Could I get your full name?",
        "email": "What's the best email to reach you at?",
        "company": "Which company are you with (if any)?",
        "role": "What's your role there?",
        "use_case": "What would you use Lenskart for (e.g., team purchase, personal prescription, contact lenses)?",
        "team_size": "How many people are in your team?",
        "timeline": "What's your expected timeline? (now / soon / later)"
    }
    for f in order:
        if not lead.get(f):
            return {"field": f, "question": labels[f], "required": True}
    # all present
    return {"field": "", "question": "", "required": False}

# ------- Murf TTS voices (session-level TTS intentionally NOT set) ------
TTS_SDR = murf.TTS(
    voice="en-US-matthew",
    style="Conversation",
    tokenizer=tokenize.basic.SentenceTokenizer(min_sentence_len=2),
    text_pacing=True,
)

# ------- SDR Agent class -------
class LenskartSDRAgent(Agent):
    def __init__(self):
        instructions = f"""
You are a friendly Lenskart SDR (voice-first). Use the provided tools—find_faq, fill_lead_field, ask_next_field, save_lead, get_lead_summary—to answer product questions and capture leads.

Important rules:
- For any product/company/pricing question, call `find_faq(question)` and answer ONLY using returned FAQ entries.
- Fill lead fields deterministically using `fill_lead_field(field, value)`.
- If you need to solicit missing lead data, call `ask_next_field()`; it returns a (field, question).
- When all required fields are collected or the user says 'thanks' / 'that's all' / 'i'm done' / 'bye', call `save_lead(lead)` then `get_lead_summary(lead)` and speak the recap.
- Keep responses short and polite, and confirm important values (e.g., repeat email back for confirmation).

You can reference the demo screenshot at: {FILE_URL}
"""
        super().__init__(instructions=instructions, tts=TTS_SDR)

    async def on_enter(self) -> None:
        greeting = (
            f"Hi — welcome to {FAQ.get('company')}. I'm here to help with frames, sunglasses, contact lenses and home eye check-ups. "
            "What brought you here today?"
        )
        await self.session.generate_reply(instructions=greeting)

# ------- Prewarm VAD -------
def prewarm(proc: JobProcess):
    proc.userdata["vad"] = silero.VAD.load()

# ------- Entrypoint -------
async def entrypoint(ctx: JobContext):
    ctx.log_context_fields = {"room": ctx.room.name}

    session = AgentSession(
        stt=deepgram.STT(model="nova-3"),
        llm=google.LLM(model="gemini-2.5-flash"),
        # DO NOT set session-level tts so agent-level TTS is used
        turn_detection=MultilingualModel(),
        vad=ctx.proc.userdata["vad"],
        preemptive_generation=True,
        tools=[find_faq, fill_lead_field, ask_next_field, save_lead, get_lead_summary],
    )

    # initialize deterministic lead state
    session.userdata = {
        "lead": {"name": None, "email": None, "company": None, "role": None, "use_case": None, "team_size": None, "timeline": None},
        "asked": []
    }

    usage_collector = metrics.UsageCollector()

    @session.on("metrics_collected")
    def _on_metrics_collected(ev: MetricsCollectedEvent):
        metrics.log_metrics(ev.metrics)
        usage_collector.collect(ev.metrics)

    async def log_usage():
        logger.info("Usage summary: %s", usage_collector.get_summary())

    ctx.add_shutdown_callback(log_usage)

    await session.start(agent=LenskartSDRAgent(), room=ctx.room, room_input_options=RoomInputOptions(noise_cancellation=noise_cancellation.BVC()))
    await ctx.connect()

if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint, prewarm_fnc=prewarm))
