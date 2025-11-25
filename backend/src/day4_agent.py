# backend/src/agent_day4.py
"""
Day 4 - Teach-the-Tutor Agent (submission-ready)

Features:
- Voices (Murf Falcon): learn -> Matthew, quiz -> Alicia, teach_back -> Ken
- STT: Deepgram (nova-3)
- LLM: Google Gemini 2.5 Flash
- Loads content from backend/shared-data/day4_tutor_content.json
- Persists mastery to backend/tutor_state/tutor_state.json (or DB if available)
- Passes RoomInputOptions to session.start (LiveKit compatibility)
- Tools for list_concepts, set_concept, explain_concept, get_mcq, evaluate_mcq,
  evaluate_teachback, get_mastery_report, get_weakness_analysis, get_learning_path, set_mode
"""

import os
import re
import json
import logging
from typing import List, Dict, Any

from dotenv import load_dotenv

# Optional DB support
try:
    from .database import init_db, save_mastery, load_mastery
    USE_DATABASE = True
except Exception:
    USE_DATABASE = False

# LiveKit / plugins
from livekit.agents import (
    Agent,
    AgentSession,
    JobContext,
    JobProcess,
    RoomInputOptions,
    WorkerOptions,
    cli,
    RunContext,
    function_tool,
)
from livekit.plugins import google, murf, deepgram, silero, noise_cancellation
from livekit.plugins.turn_detector.multilingual import MultilingualModel

load_dotenv(".env.local")
logger = logging.getLogger("day4.tutor")
logging.basicConfig(level=logging.INFO)

# -----------------------
# Paths & constants
# -----------------------
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SHARED_DATA_DIR = os.path.join(ROOT, "shared-data")
CONTENT_PATH = os.path.join(SHARED_DATA_DIR, "day4_tutor_content.json")
STATE_DIR = os.path.join(ROOT, "tutor_state")
os.makedirs(STATE_DIR, exist_ok=True)
STATE_PATH = os.path.join(STATE_DIR, "tutor_state.json")

# Voices
VOICE_LEARN = "Matthew"
VOICE_QUIZ = "Alicia"
VOICE_TEACH = "Ken"

# -----------------------
# Content & state helpers
# -----------------------
def load_content() -> List[Dict[str, Any]]:
    if not os.path.exists(CONTENT_PATH):
        logger.error("Day4 content file not found at %s", CONTENT_PATH)
        return []
    with open(CONTENT_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def load_state() -> Dict[str, Any]:
    if USE_DATABASE:
        try:
            return {"last_mode": None, "last_concept": None, "mastery": load_mastery()}
        except Exception as e:
            logger.warning("Database load failed: %s", e)

    if not os.path.exists(STATE_PATH):
        return {"last_mode": None, "last_concept": None, "mastery": {}}
    try:
        with open(STATE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.warning("Failed to load state: %s", e)
        return {"last_mode": None, "last_concept": None, "mastery": {}}

def save_state(state: Dict[str, Any]):
    if USE_DATABASE:
        try:
            mastery = state.get("mastery", {})
            for concept_id, data in mastery.items():
                save_mastery(concept_id, data)
            return
        except Exception as e:
            logger.warning("Database save failed: %s", e)

    try:
        with open(STATE_PATH, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error("Failed to save state: %s", e)

# -----------------------
# Voice switching helper
# -----------------------
def switch_session_voice(session: AgentSession, new_voice: str) -> bool:
    """Switch the session's TTS voice by replacing TTS instances if possible."""
    try:
        logger.info(f"Switching session voice to: {new_voice}")
        new_tts = murf.TTS(voice=new_voice, style="Conversation", text_pacing=True)

        updated = False
        # Common attribute names tried (robust)
        if hasattr(session, "tts"):
            try:
                session.tts = new_tts
                updated = True
            except Exception:
                logger.debug("Couldn't set session.tts directly")

        if hasattr(session, "_tts"):
            try:
                session._tts = new_tts
                updated = True
            except Exception:
                logger.debug("Couldn't set session._tts directly")

        # Some agent internals store tts on agent output
        if hasattr(session, "_agent_output"):
            try:
                ao = getattr(session, "_agent_output")
                if hasattr(ao, "_tts"):
                    ao._tts = new_tts
                    updated = True
            except Exception:
                logger.debug("Couldn't update _agent_output._tts")

        if updated:
            logger.info(f"✓ Session voice switched to {new_voice}")
        else:
            logger.warning("No TTS attributes found to update")
        return updated
    except Exception as e:
        logger.exception("Voice switch failed: %s", e)
        return False

# -----------------------
# Scoring / evaluation helpers
# -----------------------
def score_explanation(reference: str, user_text: str) -> Dict[str, Any]:
    """Return a score (0-100) with feedback, coverage, and precision metrics."""
    def words(s):
        return re.findall(r"\w+", (s or "").lower())

    ref_words = set(words(reference))
    user_words = set(words(user_text))

    if not ref_words:
        return {"score": 0, "feedback": "No reference available to score against."}
    if not user_words:
        return {"score": 0, "feedback": "Please provide an explanation to evaluate."}

    common = ref_words & user_words
    coverage_ratio = len(common) / len(ref_words)
    precision_ratio = len(common) / len(user_words) if user_words else 0

    key_terms = {"variable", "loop", "function", "condition", "if", "else", "for", "while", "def", "return"}
    ref_key_terms = ref_words & key_terms
    user_key_terms = user_words & key_terms
    key_term_score = len(user_key_terms & ref_key_terms) / max(len(ref_key_terms), 1) if ref_key_terms else 1

    score = int(min(100, round(
        coverage_ratio * 40 +
        precision_ratio * 30 +
        key_term_score * 30
    )))

    if score >= 90:
        fb = "Outstanding! You demonstrated deep understanding with precise terminology."
    elif score >= 80:
        fb = "Excellent! You covered the key concepts clearly and accurately."
    elif score >= 70:
        fb = "Good work! You understand the main ideas. Try to be more precise with technical terms."
    elif score >= 60:
        fb = "Decent attempt! You got some key points but missed important details. Review the concept again."
    elif score >= 40:
        fb = "You're on the right track but need to cover more core concepts. Focus on the main definition."
    else:
        fb = "Keep trying! Make sure to explain the basic purpose and give a simple example."

    missing_key_terms = ref_key_terms - user_key_terms
    if missing_key_terms and score < 80:
        fb += f" Try mentioning: {', '.join(list(missing_key_terms)[:3])}."

    return {"score": score, "feedback": fb, "coverage": round(coverage_ratio * 100), "precision": round(precision_ratio * 100)}

# -----------------------
# Function tools exposed to the LLM / agent
# -----------------------
@function_tool
async def list_concepts(ctx: RunContext[dict]):
    content = load_content()
    if not content:
        return "No concepts available."
    lines = [f"- {c['id']}: {c.get('title','')}" for c in content]
    return "Available concepts:\n" + "\n".join(lines)

@function_tool
async def set_concept(ctx: RunContext[dict], concept_id: str):
    content = load_content()
    cid = (concept_id or "").strip()
    match = next((c for c in content if c["id"] == cid), None)
    if not match:
        return f"Concept '{cid}' not found. Use list_concepts to see IDs."
    ctx.userdata.setdefault("tutor", {})["concept_id"] = cid
    state = load_state()
    state["last_concept"] = cid
    save_state(state)
    return f"Concept set to: {match.get('title', cid)}"

@function_tool
async def explain_concept(ctx: RunContext[dict]):
    cid = ctx.userdata.get("tutor", {}).get("concept_id")
    if not cid:
        return "No concept selected. Use set_concept to pick one."
    content = load_content()
    match = next((c for c in content if c["id"] == cid), None)
    if not match:
        return "Selected concept not found."
    state = load_state()
    state.setdefault("mastery", {})
    ms = state["mastery"].get(cid, {"times_explained": 0, "times_quizzed": 0, "times_taught_back": 0, "last_score": None, "avg_score": None})
    ms["times_explained"] = ms.get("times_explained", 0) + 1
    state["mastery"][cid] = ms
    save_state(state)
    return f"{match.get('title')}: {match.get('summary')}"

@function_tool
async def get_mcq(ctx: RunContext[dict]):
    cid = ctx.userdata.get("tutor", {}).get("concept_id")
    if not cid:
        return {"error": "No concept selected"}
    content = load_content()
    match = next((c for c in content if c["id"] == cid), None)
    if not match:
        return {"error": "Concept not found"}
    questions = match.get("quiz", []) or match.get("mcq", [])
    if not questions:
        return {"error": "No quiz questions for this concept"}
    idx = ctx.userdata.get("tutor", {}).get("quiz_index", 0) % len(questions)
    ctx.userdata.setdefault("tutor", {})["quiz_index"] = idx + 1
    q = questions[idx]
    # Return question+options but do NOT return answer
    return {"question": q.get("question"), "options": q.get("options"), "index": idx}

@function_tool
async def evaluate_mcq(ctx: RunContext[dict], user_answer: str):
    cid = ctx.userdata.get("tutor", {}).get("concept_id")
    if not cid:
        return {"error": "No concept selected"}
    content = load_content()
    match = next((c for c in content if c["id"] == cid), None)
    if not match:
        return {"error": "Concept not found"}
    questions = match.get("quiz", []) or match.get("mcq", [])
    if not questions:
        return {"error": "No questions"}
    idx = (ctx.userdata.get("tutor", {}).get("quiz_index", 1) - 1)
    if idx < 0 or idx >= len(questions):
        idx = max(0, len(questions) - 1)
    q = questions[idx]
    correct_i = q.get("answer")
    options = q.get("options", [])
    ua = (user_answer or "").lower().strip()

    # Try parse letter a/b/c/d
    sel = None
    m = re.search(r"\b([abcd])\b", ua)
    if m:
        sel = ord(m.group(1)) - 97
    else:
        m2 = re.search(r"\b([1-4])\b", ua)
        if m2:
            sel = int(m2.group(1)) - 1

    if sel is None:
        for i, opt in enumerate(options):
            if opt.lower() in ua:
                sel = i
                break

    if sel is None:
        ua_words = set(re.findall(r"\w+", ua))
        best_i = None
        best_score = 0
        for i, opt in enumerate(options):
            opt_words = set(re.findall(r"\w+", opt.lower()))
            common = ua_words & opt_words
            if len(common) > best_score:
                best_score = len(common)
                best_i = i
        if best_score >= 1:
            sel = best_i

    if sel is None:
        for w in re.findall(r"\w+", options[correct_i].lower()):
            if w in ua:
                sel = correct_i
                break

    correct = (sel == correct_i)
    feedback = ("Correct — well done!" if correct else f"Not quite. Correct answer: {options[correct_i]}.")
    state = load_state()
    state.setdefault("mastery", {})
    ms = state["mastery"].get(cid, {"times_explained": 0, "times_quizzed": 0, "times_taught_back": 0, "last_score": None, "avg_score": None})
    ms["times_quizzed"] = ms.get("times_quizzed", 0) + 1
    sc = 100 if correct else 0
    ms["last_score"] = sc
    prev = ms.get("avg_score")
    ms["avg_score"] = sc if prev is None else round((prev + sc) / 2, 1)
    state["mastery"][cid] = ms
    save_state(state)

    return {"correct": bool(correct), "selected": sel, "correct_index": correct_i, "feedback": feedback}

@function_tool
async def evaluate_teachback(ctx: RunContext[dict], explanation: str):
    cid = ctx.userdata.get("tutor", {}).get("concept_id")
    if not cid:
        return {"error": "No concept selected"}
    content = load_content()
    match = next((c for c in content if c["id"] == cid), None)
    if not match:
        return {"error": "Concept not found"}
    result = score_explanation(match.get("summary", ""), explanation or "")
    state = load_state()
    state.setdefault("mastery", {})
    ms = state["mastery"].get(cid, {"times_explained": 0, "times_quizzed": 0, "times_taught_back": 0, "last_score": None, "avg_score": None})
    ms["times_taught_back"] = ms.get("times_taught_back", 0) + 1
    ms["last_score"] = result["score"]
    prev = ms.get("avg_score")
    ms["avg_score"] = result["score"] if prev is None else round((prev + result["score"]) / 2, 1)
    state["mastery"][cid] = ms
    save_state(state)
    return result

@function_tool
async def get_mastery_report(ctx: RunContext[dict]):
    state = load_state()
    mastery = state.get("mastery", {})
    if not mastery:
        return "No mastery data yet."
    lines = ["📊 MASTERY REPORT:"]
    for cid, info in mastery.items():
        avg = info.get('avg_score', 0) or 0
        status = "🟢 Strong" if avg >= 80 else "🟡 Developing" if avg >= 60 else "🔴 Needs Work"
        lines.append(f"{cid}: {status} (avg: {avg}%, attempts: {info.get('times_quizzed', 0) + info.get('times_taught_back', 0)})")
    return "\n".join(lines)

@function_tool
async def get_weakness_analysis(ctx: RunContext[dict]):
    state = load_state()
    mastery = state.get("mastery", {})
    if not mastery:
        return "No learning data yet. Try some quizzes or teach-back sessions first!"
    concept_scores = []
    for cid, info in mastery.items():
        avg_score = info.get('avg_score', 0) or 0
        attempts = info.get('times_quizzed', 0) + info.get('times_taught_back', 0)
        if attempts > 0:
            concept_scores.append((cid, avg_score, attempts))
    if not concept_scores:
        return "No scored attempts yet. Try taking some quizzes!"
    concept_scores.sort(key=lambda x: x[1])
    lines = ["🎯 WEAKNESS ANALYSIS:"]
    weakest = concept_scores[:3]
    lines.append("\n📉 Focus on these concepts:")
    for i, (cid, score, attempts) in enumerate(weakest, 1):
        lines.append(f"{i}. {cid}: {score}% avg ({attempts} attempts)")
    if weakest:
        worst_concept = weakest[0][0]
        lines.append(f"\n💡 RECOMMENDATION: Focus on '{worst_concept}' - try teach-back mode for deeper understanding!")
    return "\n".join(lines)

@function_tool
async def get_learning_path(ctx: RunContext[dict]):
    state = load_state()
    mastery = state.get("mastery", {})
    content = load_content()
    learning_order = ["variables", "conditions", "loops", "functions"]
    lines = ["🛤️ PERSONALIZED LEARNING PATH:"]
    for i, concept_id in enumerate(learning_order, 1):
        concept_info = next((c for c in content if c["id"] == concept_id), None)
        if not concept_info:
            continue
        title = concept_info.get("title", concept_id)
        mastery_info = mastery.get(concept_id, {})
        avg_score = mastery_info.get('avg_score', 0) or 0
        attempts = mastery_info.get('times_quizzed', 0) + mastery_info.get('times_taught_back', 0)
        if avg_score >= 80:
            status = "✅ Mastered"
        elif avg_score >= 60:
            status = "🔄 Review Needed"
        elif attempts > 0:
            status = "❌ Struggling"
        else:
            status = "⭐ Not Started"
        lines.append(f"{i}. {title}: {status}")
        if avg_score < 60 and attempts > 0:
            lines.append(f"   → Try teach-back mode for {concept_id}")
        elif attempts == 0:
            lines.append(f"   → Start with learn mode for {concept_id}")
    return "\n".join(lines)

@function_tool
async def set_mode(ctx: RunContext[dict], mode: str):
    m = (mode or "").strip().lower()
    if m not in ("learn", "quiz", "teach_back"):
        return "Unknown mode. Choose 'learn', 'quiz', or 'teach_back'."
    ctx.userdata.setdefault("tutor", {})["mode"] = m
    state = load_state()
    state["last_mode"] = m
    save_state(state)
    voice_map = {"learn": VOICE_LEARN, "quiz": VOICE_QUIZ, "teach_back": VOICE_TEACH}
    new_voice = voice_map.get(m, VOICE_LEARN)
    session_ref = ctx.userdata.get('_session_ref')
    if session_ref:
        switch_session_voice(session_ref, new_voice)
    return f"Mode set to: {m}. Voice switched to {new_voice}."

# -----------------------
# Tutor Agent
# -----------------------
class TutorAgent(Agent):
    def __init__(self, content: List[dict]):
        instructions = """You are an Active Recall Tech Tutor with three modes:

LEARN MODE (Matthew voice): Explain concepts clearly and thoroughly
QUIZ MODE (Alicia voice): Ask multiple-choice questions energetically
TEACH-BACK MODE (Ken voice): Listen to student explanations supportively

Use the provided tools for each action. Keep responses short and mode-appropriate.
"""
        super().__init__(instructions=instructions, tools=[
            list_concepts, set_concept, set_mode, explain_concept, get_mcq,
            evaluate_mcq, evaluate_teachback, get_mastery_report,
            get_weakness_analysis, get_learning_path
        ])
        self.content = content
        self._session = None

# -----------------------
# Prewarm
# -----------------------
def prewarm(proc: JobProcess):
    try:
        proc.userdata["vad"] = silero.VAD.load()
    except Exception as e:
        logger.warning("VAD prewarm failed: %s", e)
        proc.userdata["vad"] = None

# -----------------------
# Entrypoint
# -----------------------
async def entrypoint(ctx: JobContext):
    ctx.log_context_fields = {"room": ctx.room.name}
    logger.info("Starting Day4 tutor - room %s", ctx.room.name)

    if USE_DATABASE:
        try:
            init_db()
            logger.info("Database initialized")
        except Exception as e:
            logger.warning("Database init failed: %s", e)

    content = load_content()
    if not content:
        logger.error("No content loaded. Please add day4_tutor_content.json")

    userdata = {"tutor": {"mode": None, "concept_id": None, "quiz_index": 0}, "history": []}

    session = AgentSession(
        stt=deepgram.STT(model="nova-3", api_key=os.getenv("DEEPGRAM_API_KEY")),
        llm=google.LLM(model="gemini-2.5-flash", api_key=os.getenv("GOOGLE_API_KEY")),
        tts=murf.TTS(voice=VOICE_LEARN, style="Conversation", text_pacing=True, api_key=os.getenv("MURF_API_KEY")),
        turn_detection=MultilingualModel(),
        vad=ctx.proc.userdata.get("vad"),
        userdata=userdata,
    )

    agent = TutorAgent(content)
    agent._session = session

    await session.start(
        agent=agent,
        room=ctx.room,
        room_input_options=RoomInputOptions(noise_cancellation=noise_cancellation.BVC())
    )

    agent._session = session
    session.userdata['_session_ref'] = session

    await ctx.connect()

# -----------------------
# Run worker
# -----------------------
if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint, prewarm_fnc=prewarm))
