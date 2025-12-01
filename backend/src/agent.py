"""
Improv Battle host agent — clean implementation.
This file implements a LiveKit agent that runs a short improv show with a voice host.
"""

import os
import json
import logging
from typing import Optional, Annotated
from dataclasses import dataclass, field
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import unquote

from dotenv import load_dotenv
from pydantic import Field
from livekit.agents import (
    Agent,
    AgentSession,
    JobContext,
    JobProcess,
    RoomInputOptions,
    WorkerOptions,
    cli,
    function_tool,
    RunContext,
)
from livekit.plugins import murf, silero, openai, deepgram, noise_cancellation
from livekit.plugins.turn_detector.multilingual import MultilingualModel

# -------------------------
# Setup
# -------------------------
load_dotenv(".env.local")

logger = logging.getLogger("improv_agent")
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
logger.addHandler(handler)

# In-memory mapping of room name -> improv_state (dict)
SESSIONS: dict = {}
_STATE_SERVER_STARTED = False


# -------------------------
# Data models
# -------------------------
@dataclass
class Userdata:
    user_name: Optional[str] = None
    improv_state: dict = field(default_factory=lambda: {
        "player_name": None,
        "current_round": 0,
        "max_rounds": 3,
        "rounds": [],
        "phase": "intro",
    })


# -------------------------
# Improv State HTTP server
# -------------------------
def _make_state_handler():
    class StateHandler(BaseHTTPRequestHandler):
        def _send_json(self, obj, status=200):
            data = json.dumps(obj, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            path = self.path
            if path.startswith("/improv/state/"):
                room = unquote(path[len("/improv/state/"):])
                state = SESSIONS.get(room)
                if state is None:
                    self._send_json({"error": "room not found"}, status=404)
                    return
                self._send_json(state)
                return

            if path == "/health":
                self._send_json({"ok": True})
                return

            self._send_json({"error": "not found"}, status=404)

        def do_POST(self):
            path = self.path
            if path.startswith("/improv/stop/"):
                room = unquote(path[len("/improv/stop/"):])
                state = SESSIONS.get(room)
                if state is None:
                    self._send_json({"error": "room not found"}, status=404)
                    return
                state["phase"] = "done"
                self._send_json({"ok": True})
                return
            self._send_json({"error": "not found"}, status=404)

    return StateHandler


def start_state_server(port: int = 9001):
    global _STATE_SERVER_STARTED
    if _STATE_SERVER_STARTED:
        return
    handler = _make_state_handler()

    def _serve():
        try:
            server = ThreadingHTTPServer(("0.0.0.0", port), handler)
            logger.info(f"State server listening on http://0.0.0.0:{port}")
            server.serve_forever()
        except Exception as e:
            logger.error(f"State server failed: {e}")

    t = threading.Thread(target=_serve, daemon=True)
    t.start()
    _STATE_SERVER_STARTED = True


# -------------------------
# Improv Battle Agent
# -------------------------
SCENARIOS = [
    "You are a barista who has to tell a customer that their latte is actually a portal to another dimension.",
    "You are a time-travelling tour guide explaining modern smartphones to someone from the 1800s.",
    "You are a restaurant waiter who must calmly tell a customer that their order has escaped the kitchen.",
    "You are a customer trying to return an obviously cursed object to a very skeptical shop owner.",
    "You are a medieval scribe accidentally transcribing a sci-fi podcast and trying to make it make sense.",
]


@function_tool
async def get_next_scenario(ctx: RunContext[Userdata]) -> str:
    state = ctx.userdata.improv_state
    idx = state.get("current_round", 0)
    max_rounds = state.get("max_rounds", 3)
    if idx >= max_rounds:
        return "__NO_MORE_ROUNDS__"
    scenario = SCENARIOS[idx % len(SCENARIOS)]
    state["phase"] = "awaiting_improv"
    state["current_round"] = idx + 1
    state["rounds"].append({"scenario": scenario, "host_reaction": None})
    return scenario


@function_tool
async def record_reaction(ctx: RunContext[Userdata], reaction: Annotated[str, Field(description="Host reaction text")]) -> str:
    state = ctx.userdata.improv_state
    idx = state.get("current_round", 0) - 1
    if idx < 0 or idx >= len(state.get("rounds", [])):
        return "No active round to record reaction for."
    state["rounds"][idx]["host_reaction"] = reaction
    if state.get("current_round", 0) >= state.get("max_rounds", 3):
        state["phase"] = "done"
    else:
        state["phase"] = "reacting"
    return "OK"


class ImprovBattleAgent(Agent):
    def __init__(self):
        super().__init__(
            instructions=f"""
            You are the host of a TV improv show called 'Improv Battle'.
            Role: Host persona — high-energy, witty, and clear about rules.
            Structure:
            - Introduce the show and explain the basic rules.
            - Run `{{max_rounds}}` improv rounds. For each round:
              1) Announce the scenario and tell the player to start improvising.
              2) Wait for the player's performance (they will speak or say 'End scene').
              3) After the player's turn, react with a short, varied, realistic reaction and call `record_reaction` to store the reaction.
            Behaviour:
            - Reactions should be randomly supportive, neutral, or mildly critical but always constructive and respectful.
            - Use `get_next_scenario` to obtain scenarios and transition the state into `awaiting_improv`.
            - At the end, summarize the player's style (character work, absurdity, emotional range), mention 1-2 standout moments, thank the player, and close the show.
            - Respect safe content rules; do not produce abusive language.
            """ ,
            tools=[get_next_scenario, record_reaction],
        )


# -------------------------
# Entrypoint
# -------------------------
def prewarm(proc: JobProcess):
    try:
        proc.userdata["vad"] = silero.VAD.load()
    except Exception:
        logger.warning("VAD prewarm failed; continuing without preloaded VAD.")


async def entrypoint(ctx: JobContext):
    ctx.log_context_fields = {"room": ctx.room.name}
    agent_mode = os.environ.get("AGENT_MODE", "improv").lower()
    logger.info("\n🎭 Starting Improv Battle Host Agent")

    session = AgentSession(
        stt=deepgram.STT(model="nova-3"),
        llm=openai.LLM(model="gpt-4o-mini"),
        tts=murf.TTS(
            voice="en-US-natalie",
            style="Conversational",
            text_pacing=True,
        ),
        turn_detection=MultilingualModel(),
        vad=ctx.proc.userdata.get("vad"),
        userdata=Userdata(),
    )

    # Start a small state server to expose improv_state for tooling / frontend polling
    try:
        start_state_server(port=int(os.environ.get("IMPROV_STATE_PORT", "9001")))
    except Exception:
        logger.exception("Failed to start state server")

    chosen_agent = ImprovBattleAgent()

    await session.start(
        agent=chosen_agent,
        room=ctx.room,
        room_input_options=RoomInputOptions(noise_cancellation=noise_cancellation.BVC()),
    )

    try:
        SESSIONS[ctx.room.name] = session.userdata.improv_state
    except Exception:
        logger.exception("Failed to register session improv state")

    logger.info("✅ Agent session started with real-time transcription enabled")
    await ctx.connect()


if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint, prewarm_fnc=prewarm))
