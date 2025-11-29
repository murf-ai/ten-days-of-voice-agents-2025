# backend/src/agent_day4.py
"""
Day 4 - Teach-the-Tutor Agent (fixed version)

- Voices (Murf Falcon):
    learn     -> Matthew
    quiz      -> Alicia
    teach_back-> Ken

- STT: Deepgram nova-3
- LLM: Google Gemini 2.5 Flash
- Loads content from backend/shared-data/day4_tutor_content.json
- Persists mastery to backend/tutor_state/tutor_state.json
- Passes RoomInputOptions to session.start (LiveKit API compatibility)
"""

import os
import re
import json
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime

from dotenv import load_dotenv

# livekit agents imports
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

# -----------------------
# Paths & constants
# -----------------------
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SHARED_DATA_DIR = os.path.join(ROOT, "shared-data")
CONTENT_PATH = os.path.join(SHARED_DATA_DIR, "day4_tutor_content.json")
STATE_DIR = os.path.join(ROOT, "tutor_state")
os.makedirs(STATE_DIR, exist_ok=True)
STATE_PATH = os.path.join(STATE_DIR, "tutor_state.json")

# Voice mapping
VOICE_LEARN = "Matthew"
VOICE_QUIZ = "Anusha"
VOICE_TEACH = "Ken"

# -----------------------
# Helpers: load/save
# -----------------------
def load_content() -> List[Dict[str, Any]]:
    if not os.path.exists(CONTENT_PATH):
        logger.error("Day4 content file not found at %s", CONTENT_PATH)
        return []
    with open(CONTENT_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def load_state() -> Dict[str, Any]:
    if not os.path.exists(STATE_PATH):
        return {"last_mode": None, "last_concept": None, "mastery": {}}
    try:
        with open(STATE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.warning("Failed to load state: %s", e)
        return {"last_mode": None, "last_concept": None, "mastery": {}}

def save_state(state: Dict[str, Any]):
    try:
        with open(STATE_PATH, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error("Failed to save state: %s", e)

# -----------------------
# Voice switching helper
# -----------------------
def switch_session_voice(session: AgentSession, new_voice: str):
    """Switch the session's TTS voice by replacing the TTS instance"""
    try:
        logger.info(f"🎤 Switching session voice to: {new_voice}")
        logger.info(f"Session type: {type(session)}")
        logger.info(f"Session attributes: {[attr for attr in dir(session) if 'tts' in attr.lower()]}")
        
        new_tts = murf.TTS(
            voice=new_voice,
            style="Conversation",
            text_pacing=True
        )
        
        # Try multiple ways to replace TTS
        updated = False
        if hasattr(session, '_tts'):
            old_tts = getattr(session, '_tts', None)
            session._tts = new_tts
            logger.info(f"Updated session._tts from {old_tts} to {new_tts}")
            updated = True
            
        if hasattr(session, 'tts'):
            old_tts = getattr(session, 'tts', None)
            session.tts = new_tts
            logger.info(f"Updated session.tts from {old_tts} to {new_tts}")
            updated = True
        
        # Force update internal TTS references
        try:
            if hasattr(session, '_agent_output') and hasattr(session._agent_output, '_tts'):
                session._agent_output._tts = new_tts
                logger.info("Updated session._agent_output._tts")
                updated = True
        except Exception as e:
            logger.warning(f"Could not update _agent_output._tts: {e}")
            
        if updated:
            logger.info(f"✓ Session voice switched to {new_voice}")
        else:
            logger.warning("No TTS attributes found to update")
            
        return updated
    except Exception as e:
        logger.error(f"Voice switch failed: {e}", exc_info=True)
        return False

# -----------------------
# Small evaluation helpers
# -----------------------
def score_explanation(reference: str, user_text: str) -> Dict[str, Any]:
    """Simple overlap-based scoring (0-100) + short feedback."""
    def words(s):
        return re.findall(r"\w+", (s or "").lower())
    ref_words = set(words(reference))
    user_words = set(words(user_text))
    if not ref_words:
        return {"score": 0, "feedback": "No reference available to score against."}
    common = ref_words & user_words
    ratio = len(common) / max(len(ref_words), 1)
    score = int(min(100, round(ratio * 100)))
    if score >= 80:
        fb = "Excellent — you covered the key points clearly."
    elif score >= 50:
        fb = "Good — you covered several ideas but missed some details."
    else:
        fb = "Nice attempt — try to state the core idea and one short example."
    return {"score": score, "feedback": fb}

# -----------------------
# Tools exposed to LLM / agent flow
# -----------------------
@function_tool
async def list_concepts(ctx: RunContext[dict]):
    """List all available programming concepts that can be learned."""
    content = load_content()
    if not content:
        return "No concepts available."
    lines = [f"- {c['id']}: {c.get('title','')}" for c in content]
    return "Available concepts:\n" + "\n".join(lines)

@function_tool
async def set_concept(ctx: RunContext[dict], concept_id: str):
    """Select a concept by its ID to work with (e.g., 'variables', 'loops')."""
    content = load_content()
    cid = (concept_id or "").strip()
    match = next((c for c in content if c["id"] == cid), None)
    if not match:
        return f"Concept '{cid}' not found. Use list_concepts to see IDs."
    ctx.userdata["tutor"]["concept_id"] = cid
    state = load_state()
    state["last_concept"] = cid
    save_state(state)
    return f"Concept set to: {match.get('title', cid)}"



@function_tool
async def explain_concept(ctx: RunContext[dict]):
    """Explain the currently selected concept in detail."""
    cid = ctx.userdata["tutor"].get("concept_id")
    if not cid:
        return "No concept selected. Use set_concept to pick one."
    content = load_content()
    match = next((c for c in content if c["id"] == cid), None)
    if not match:
        return "Selected concept not found."
    # Mark explained count
    state = load_state()
    state.setdefault("mastery", {})
    ms = state["mastery"].get(cid, {"times_explained": 0, "times_quizzed": 0, "times_taught_back": 0, "last_score": None, "avg_score": None})
    ms["times_explained"] = ms.get("times_explained", 0) + 1
    state["mastery"][cid] = ms
    save_state(state)
    return f"{match.get('title')}: {match.get('summary')}"

@function_tool
async def get_mcq(ctx: RunContext[dict]):
    """Get the next multiple-choice quiz question for the selected concept."""
    cid = ctx.userdata["tutor"].get("concept_id")
    if not cid:
        return {"error": "No concept selected"}
    content = load_content()
    match = next((c for c in content if c["id"] == cid), None)
    if not match:
        return {"error": "Concept not found"}
    questions = match.get("quiz", []) or match.get("mcq", [])
    if not questions:
        return {"error": "No quiz questions for this concept"}
    # maintain rotation index in userdata
    idx = ctx.userdata["tutor"].get("quiz_index", 0) % len(questions)
    ctx.userdata["tutor"]["quiz_index"] = idx + 1
    q = questions[idx]
    return {"question": q["question"], "options": q["options"], "answer": q["answer"], "index": idx}

@function_tool
async def evaluate_mcq(ctx: RunContext[dict], user_answer: str):
    """Score the user's multiple-choice quiz answer and return feedback."""
    cid = ctx.userdata["tutor"].get("concept_id")
    if not cid:
        return {"error": "No concept selected"}
    content = load_content()
    match = next((c for c in content if c["id"] == cid), None)
    if not match:
        return {"error": "Concept not found"}
    # fetch last asked question index
    idx = (ctx.userdata["tutor"].get("quiz_index", 1) - 1)
    questions = match.get("quiz", []) or match.get("mcq", [])
    if not questions:
        return {"error": "No questions"}
    if idx < 0 or idx >= len(questions):
        idx = max(0, len(questions) - 1)
    q = questions[idx]
    correct_i = q["answer"]
    options = q["options"]
    ua = (user_answer or "").lower().strip()

    # 1) letter (a/b/c/d)
    sel = None
    m = re.search(r"\b([abcd])\b", ua)
    if m:
        sel = ord(m.group(1)) - 97
    else:
        # number 1-4
        m2 = re.search(r"\b([1-4])\b", ua)
        if m2:
            sel = int(m2.group(1)) - 1

    # 2) match option text
    if sel is None:
        for i, opt in enumerate(options):
            if opt.lower() in ua:
                sel = i
                break
    # 3) partial overlap heuristic
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

    # 4) final fallback check for any keyword from correct option
    if sel is None:
        for w in re.findall(r"\w+", options[correct_i].lower()):
            if w in ua:
                sel = correct_i
                break

    correct = (sel == correct_i)
    feedback = ("Correct — well done!" if correct else f"Not quite. Correct answer: {options[correct_i]}.")
    # update mastery
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
    """Score the user's explanation in teach-back mode and return feedback."""
    cid = ctx.userdata["tutor"].get("concept_id")
    if not cid:
        return {"error": "No concept selected"}
    content = load_content()
    match = next((c for c in content if c["id"] == cid), None)
    if not match:
        return {"error": "Concept not found"}
    result = score_explanation(match.get("summary", ""), explanation or "")
    # update mastery
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
    """Get a detailed report of the user's mastery progress across all concepts."""
    state = load_state()
    mastery = state.get("mastery", {})
    if not mastery:
        return "No mastery data yet."
    lines = []
    for cid, info in mastery.items():
        lines.append(f"{cid}: last={info.get('last_score')}, avg={info.get('avg_score')}, taught_back={info.get('times_taught_back')}, quizzed={info.get('times_quizzed')}")
    return "Mastery:\n" + "\n".join(lines)



@function_tool
async def set_mode(ctx: RunContext[dict], mode: str):
    """Change the learning mode and switch voice: 'learn', 'quiz', or 'teach_back'."""
    m = (mode or "").strip().lower()
    if m not in ("learn", "quiz", "teach_back"):
        return "Unknown mode. Choose 'learn', 'quiz', or 'teach_back'."
    
    ctx.userdata["tutor"]["mode"] = m
    state = load_state()
    state["last_mode"] = m
    save_state(state)
    
    # Switch voice based on mode
    voice_map = {
        "learn": VOICE_LEARN,
        "quiz": VOICE_QUIZ,
        "teach_back": VOICE_TEACH,
    }
    
    new_voice = voice_map.get(m, VOICE_LEARN)
    session_ref = ctx.userdata.get('_session_ref')
    if session_ref:
        switch_session_voice(session_ref, new_voice)
    
    return f"Mode set to: {m}. Voice switched to {new_voice}."

# -----------------------
# Single Tutor Agent with Voice Switching
# -----------------------
class TutorAgent(Agent):
    """Active Recall Tutor with dynamic voice switching"""
    def __init__(self, content: List[dict]):
        instructions = """You are an Active Recall Tech Tutor with three modes:

LEARN MODE (Matthew voice): Explain concepts clearly and thoroughly
QUIZ MODE (Anusha voice): Ask multiple-choice questions energetically  
TEACH-BACK MODE (Ken voice): Listen to student explanations supportively

When user wants concepts:
1. Call list_concepts() to show available topics
2. Ask which concept they want

When user selects concept:
1. Call set_concept(concept_id)
2. Ask which mode they prefer

When user chooses mode:
1. Call set_mode(mode) - this switches voice automatically
2. Execute the mode:
   - Learn: Call explain_concept()
   - Quiz: Call get_mcq() then evaluate_mcq()
   - Teach-back: Ask for explanation then evaluate_teachback()

RULES:
- ALWAYS use tools, never make up responses
- Keep responses SHORT and mode-appropriate
- Voice changes automatically with set_mode
- Adapt personality to current mode"""

        super().__init__(
            instructions=instructions,
            tools=[
                list_concepts,
                set_concept,
                set_mode,
                explain_concept,
                get_mcq,
                evaluate_mcq,
                evaluate_teachback,
                get_mastery_report
            ]
        )
        self.content = content
        self._session = None
    


# -----------------------
# Prewarm function
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
    """Main entry point for the tutor agent"""
    ctx.log_context_fields = {"room": ctx.room.name}
    logger.info("Starting Day4 tutor - room %s", ctx.room.name)

    # Load content from persistent storage
    content = load_content()
    if not content:
        logger.error("No content loaded. Please add day4_tutor_content.json")

    # Initialize user data
    userdata = {
        "tutor": {
            "mode": None,
            "concept_id": None,
            "quiz_index": 0,
        },
        "history": []
    }

    # Create session with initial TTS
    session = AgentSession(
        stt=deepgram.STT(model="nova-3"),
        llm=google.LLM(model="gemini-2.5-flash", api_key=os.getenv("GOOGLE_API_KEY")),
        tts=murf.TTS(voice=VOICE_LEARN, style="Conversation", text_pacing=True),
        turn_detection=MultilingualModel(),
        vad=ctx.proc.userdata.get("vad"),
        userdata=userdata,
    )

    # Create tutor agent
    agent = TutorAgent(content)
    agent._session = session  # Pass session to agent for voice switching

    # Start session (MUST complete before event handlers are registered)
    await session.start(
        agent=agent,
        room=ctx.room,
        room_input_options=RoomInputOptions(
            noise_cancellation=noise_cancellation.BVC()
        )
    )

    # Pass session reference for voice switching
    agent._session = session
    session.userdata['_session_ref'] = session

    # Connect to room
    await ctx.connect()

# -----------------------
# Run worker
# -----------------------
if __name__ == "__main__":
    cli.run_app(
        WorkerOptions(
            entrypoint_fnc=entrypoint,
            prewarm_fnc=prewarm
        )
    )