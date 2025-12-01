# backend/src/agent_day10.py
import logging
import os
import json
from datetime import datetime
from typing import Any, Dict, List, Optional

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
from livekit.plugins import murf, silero, google, deepgram, noise_cancellation
from livekit.plugins.turn_detector.multilingual import MultilingualModel

logger = logging.getLogger("agent_day10")
logger.setLevel(logging.INFO)

load_dotenv(".env.local")

# ---------- Paths & storage ----------
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHARED_DIR = os.path.join(BASE_DIR, "shared-data")
os.makedirs(SHARED_DIR, exist_ok=True)

SCENARIOS_PATH = os.path.join(SHARED_DIR, "day10_scenarios.json")
SESSION_LOG = os.path.join(SHARED_DIR, "day10_improv_sessions.json")

# default scenarios if file missing
DEFAULT_SCENARIOS = [
    "You are a barista who must tell a customer their latte is actually a portal to another dimension.",
    "You are a time-travelling tour guide explaining smartphones to someone from the 1800s.",
    "You are a restaurant waiter who must calmly tell a customer that their order has escaped the kitchen.",
    "You are a shop owner trying to accept a return of an obviously magical (and cursed) item.",
    "You are a taxi driver who realizes the passenger is a famous disguised celebrity."
]

def load_scenarios() -> List[str]:
    if not os.path.exists(SCENARIOS_PATH):
        with open(SCENARIOS_PATH, "w", encoding="utf-8") as f:
            json.dump(DEFAULT_SCENARIOS, f, indent=2, ensure_ascii=False)
        return DEFAULT_SCENARIOS.copy()
    with open(SCENARIOS_PATH, "r", encoding="utf-8") as f:
        try:
            data = json.load(f)
            if isinstance(data, list) and all(isinstance(x, str) for x in data):
                return data
        except Exception:
            pass
    return DEFAULT_SCENARIOS.copy()

SCENARIOS = load_scenarios()

def append_session_log(entry: Dict[str, Any]):
    try:
        if not os.path.exists(SESSION_LOG):
            with open(SESSION_LOG, "w", encoding="utf-8") as f:
                json.dump([entry], f, indent=2, ensure_ascii=False)
            return
        with open(SESSION_LOG, "r+", encoding="utf-8") as f:
            data = json.load(f)
            data.append(entry)
            f.seek(0)
            json.dump(data, f, indent=2, ensure_ascii=False)
            f.truncate()
    except Exception as e:
        logger.warning("Could not write session log: %s", e)

# ---------- Murf TTS voices ----------
TTS_HOST = murf.TTS(
    voice="en-US-matthew",    # host voice - change if needed
    style="Conversational",
    tokenizer=tokenize.basic.SentenceTokenizer(min_sentence_len=2),
    text_pacing=True,
)

TTS_ROUTER = TTS_HOST

# ---------- Tools exposed to LLM / agent ---------- #

@function_tool()
async def start_game(ctx: RunContext, player_name: Optional[str] = None, max_rounds: Optional[int] = 3) -> Dict[str, Any]:
    """
    Initialize improv_state in session.userdata and return a summary.
    """
    session = ctx.session
    ud = getattr(session, "userdata", {})
    improv_state = {
        "player_name": player_name or "Guest",
        "current_round": 0,
        "max_rounds": max(1, int(max_rounds or 3)),
        "rounds": [],
        "phase": "intro"  # intro | awaiting_improv | reacting | done
    }
    ud["improv_state"] = improv_state
    session.userdata = ud
    return {"ok": True, "msg": f"Game started for {improv_state['player_name']} with {improv_state['max_rounds']} rounds."}

@function_tool()
async def next_round(ctx: RunContext) -> Dict[str, Any]:
    """
    Move to the next round: choose a scenario and set phase to awaiting_improv.
    Returns the scenario text.
    """
    session = ctx.session
    ud = getattr(session, "userdata", {})
    state = ud.get("improv_state", {})
    if not state:
        return {"error": "no_game", "msg": "No game started. Call start_game first."}
    if state["current_round"] >= state["max_rounds"]:
        state["phase"] = "done"
        ud["improv_state"] = state
        session.userdata = ud
        return {"ok": False, "msg": "All rounds completed."}

    # pick scenario (simple round-robin)
    idx = (state["current_round"]) % len(SCENARIOS)
    scenario = SCENARIOS[idx]
    state["current_round"] += 1
    state["phase"] = "awaiting_improv"
    state["rounds"].append({"round": state["current_round"], "scenario": scenario, "improv": None, "reaction": None})
    ud["improv_state"] = state
    session.userdata = ud
    return {"ok": True, "round": state["current_round"], "scenario": scenario}

@function_tool()
async def record_improv(ctx: RunContext, text: str) -> str:
    """
    Record player's improv for the current round and set phase to reacting.
    """
    session = ctx.session
    ud = getattr(session, "userdata", {})
    state = ud.get("improv_state", {})
    if not state or state.get("phase") != "awaiting_improv":
        return "No active round awaiting improv."
    # record last appended round
    if not state["rounds"]:
        return "No round to record."
    state["rounds"][-1]["improv"] = {"text": text, "ts": datetime.utcnow().isoformat()}
    state["phase"] = "reacting"
    ud["improv_state"] = state
    session.userdata = ud
    return "Recorded your performance; host will react now."

@function_tool()
async def save_reaction(ctx: RunContext, reaction_text: str) -> str:
    """
    Save host reaction for the current round and update phase.
    """
    session = ctx.session
    ud = getattr(session, "userdata", {})
    state = ud.get("improv_state", {})
    if not state or state.get("phase") != "reacting":
        return "Not currently reacting to any round."
    state["rounds"][-1]["reaction"] = {"text": reaction_text, "ts": datetime.utcnow().isoformat()}
    # if finished all rounds, set phase done else awaiting next round
    if state["current_round"] >= state["max_rounds"]:
        state["phase"] = "done"
    else:
        state["phase"] = "intro"  # allow host to trigger next_round
    ud["improv_state"] = state
    session.userdata = ud
    return "Saved host reaction."

@function_tool()
async def end_game(ctx: RunContext) -> Dict[str, Any]:
    """
    End the game early: persist session and return summary.
    """
    session = ctx.session
    ud = getattr(session, "userdata", {})
    state = ud.get("improv_state", {})
    if not state:
        return {"error": "no_game", "msg": "No game in progress."}
    # persist
    entry = {
        "ended_at": datetime.utcnow().isoformat(),
        "improv_state": state
    }
    append_session_log(entry)
    # clear state
    ud["improv_state"] = {}
    session.userdata = ud
    return {"ok": True, "msg": "Game ended and saved.", "summary": state}

@function_tool()
async def get_state(ctx: RunContext) -> Dict[str, Any]:
    session = ctx.session
    ud = getattr(session, "userdata", {})
    return ud.get("improv_state", {})

# ---------- Game Host Agent ---------- #
class ImprovHostAgent(Agent):
    def __init__(self, **kwargs):
        # Instructions do not need runtime interpolation — keep static string
        instructions = """
You are the host of a TV-style improv show called "Improv Battle".
Role: energetic, witty, constructive. Explain rules briefly, run several rounds (max provided by start_game).
Behaviour:
 - Introduce the show and ask for player's name if missing.
 - For each round: announce scenario clearly and instruct player to start improv.
   End each host message with a direct prompt: "Start improvising! When you're done, say 'End scene' or 'End'." 
 - When player finishes, give a reaction (1-3 sentences): sometimes praise, sometimes mild critique—always constructive & respectful.
 - Store reaction using save_reaction tool, record player performance using record_improv tool.
 - If player says "stop game" or "end show", call end_game and say goodbye.
 - If player says "restart", call start_game and begin fresh.
 - After final round, give short summary: strengths + 1 suggestion.
"""
        super().__init__(instructions=instructions, tts=TTS_HOST, **kwargs)

    async def on_enter(self) -> None:
        # greet and explain rules
        await self.session.generate_reply(instructions=(
            "Welcome to Improv Battle! Explain the rules in 2-3 short sentences: "
            "We will run several short improv rounds. For each round I'll give a scenario — you act it out. "
            "When you're done with a scene, say 'End scene' or 'End'. You can stop anytime by saying 'stop game'. "
            "What is your name (or tell me 'Guest')?"
        ))

    # Optionally handle some lifecycle hooks (left simple for sample)

# ---------- Prewarm VAD ---------- #
def prewarm(proc: JobProcess):
    proc.userdata["vad"] = silero.VAD.load()

# ---------- Entrypoint ---------- #
async def entrypoint(ctx: JobContext):
    ctx.log_context_fields = {"room": ctx.room.name}

    session = AgentSession(
        stt=deepgram.STT(model="nova-3"),
        llm=google.LLM(model="gemini-2.5-flash"),
        tts=None,  # agent provides TTS
        turn_detection=MultilingualModel(),
        vad=ctx.proc.userdata["vad"],
        preemptive_generation=True,
        tools=[start_game, next_round, record_improv, save_reaction, get_state, end_game],
    )

    # initialize userdata
    session.userdata = {"improv_state": {}}

    usage_collector = metrics.UsageCollector()
    @session.on("metrics_collected")
    def _on_metrics_collected(ev):
        metrics.log_metrics(ev.metrics)
        usage_collector.collect(ev.metrics)

    async def log_usage():
        logger.info("Usage summary: %s", usage_collector.get_summary())

    ctx.add_shutdown_callback(log_usage)

    await session.start(agent=ImprovHostAgent(), room=ctx.room,
                        room_input_options=RoomInputOptions(noise_cancellation=noise_cancellation.BVC()))
    await ctx.connect()

if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint, prewarm_fnc=prewarm))
