import logging
from dataclasses import dataclass, asdict
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
)
from livekit.plugins import murf, silero, google, deepgram, noise_cancellation
from livekit.plugins.turn_detector.multilingual import MultilingualModel

# --------- logging setup ---------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("agent")

load_dotenv(".env.local")


# ------------- Simple improv state container (per session) -------------


@dataclass
class ImprovRound:
    scenario: str
    host_reaction: Optional[str] = None


@dataclass
class ImprovState:
    player_name: Optional[str] = None
    current_round: int = 0
    max_rounds: int = 3
    phase: str = "intro"  # "intro" | "awaiting_improv" | "reacting" | "done"
    rounds: List[ImprovRound] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "player_name": self.player_name,
            "current_round": self.current_round,
            "max_rounds": self.max_rounds,
            "phase": self.phase,
            "rounds": [asdict(r) for r in (self.rounds or [])],
        }


# ------------- Improv Host Agent -------------


class ImprovHostAgent(Agent):
    """
    Single-player Improv Battle host.

    NOTE: The LLM controls the conversation flow, but we keep a simple
    improv_state object on the backend for bookkeeping & logging.
    """

    def __init__(self) -> None:
        # pre-defined scenarios for 3 rounds
        self.scenarios: List[str] = [
            # Round 1
            (
                "Round 1! You are a time-travelling tour guide who has landed in 1800s "
                "India. You must explain modern smartphones to a skeptical local who "
                "thinks you are some kind of magician."
            ),
            # Round 2
            (
                "Round 2! You are a restaurant waiter who must calmly tell a customer "
                "that their biryani has escaped the kitchen and is running around the city."
            ),
            # Round 3
            (
                "Final Round! You are a customer trying to return an obviously cursed "
                "object to a very skeptical shop owner who insists it is perfectly normal."
            ),
        ]

        self.improv_state = ImprovState(
            player_name=None,
            current_round=0,
            max_rounds=len(self.scenarios),
            phase="intro",
            rounds=[],
        )

        instructions = f"""
You are the high-energy host of a TV improv game show called "Improv Battle".

You are running a **single-player** improv game over voice.
The player joins from the browser with a name like "Eshwar".
Your job is to:

1) Introduce the show and rules.
2) Run exactly {self.improv_state.max_rounds} improv rounds using the fixed scenarios below.
3) After each round, react with varied, realistic feedback.
4) Give a fun closing summary when the game ends.
5) Respect early exit if the player clearly wants to stop.

------------------------
GAME STRUCTURE (YOU MUST FOLLOW)
------------------------

When the conversation starts:

- Greet the player as the host of "Improv Battle".
- Ask for their name if it is not clear yet. Once you know it, use it often.
- Briefly explain the rules, for example:
  "I'll give you 3 wild scenarios. In each one, you act it out in character.
   When you're done, say something like 'End scene' or 'I'm done',
   and I'll react and move to the next round."

Then play through these 3 rounds in order:

SCENARIO 1:
"{self.scenarios[0]}"

SCENARIO 2:
"{self.scenarios[1]}"

SCENARIO 3:
"{self.scenarios[2]}"

For each round:

1. Clearly announce the round number.
2. State the scenario with energy and clarity.
3. Tell the player to start improvising now.
   Example: "3, 2, 1... and action!"
4. Let the player speak in character for a bit.
   - The player might talk for one or more turns.
   - When they say something like "End scene", "I'm done", "Okay", or they pause,
     you should treat the scene as finished.
5. React as the host:
   - Comment on what worked, what was funny, what was weird or flat.
   - Vary your tone:
        * Sometimes amused and supportive.
        * Sometimes lightly critical or unimpressed.
        * Sometimes pleasantly surprised.
   - Always stay respectful and non-abusive.
   - Keep your reaction to 2–4 sentences.
6. Then move on to the next round, until all rounds are completed.

------------------------
HOST REACTION STYLE
------------------------

Your reactions should feel like a real improv coach / host:

- Mention specific things the player did:
  "I loved how you leaned into the idea that the phone was 'tiny magic TV'!"
- Mix praise and critique:
  - Positive: "That cursed object character had great attitude."
  - Critical but kind: "You could have slowed down and made the waiter more panicked."
- Sometimes tease the player lightly:
  - "That ending was pure chaos, and I'm honestly proud of the nonsense."
  - "You bailed out a bit early there, but the idea was solid."

Do NOT be robotic or always positive. Add variety and personality.

------------------------
CLOSING SUMMARY
------------------------

After the final round:

- Thank the player by name.
- Summarize what kind of improviser they seemed to be:
  - e.g. "very character-driven", "loves absurd scenarios", "good at emotional tone".
- Mention 1–2 specific scenes or moments that stood out.
- Close the show clearly, e.g.
  "That’s all for tonight on Improv Battle. See you next time!"

------------------------
EARLY EXIT
------------------------

If the player clearly says they want to stop the game early,
for example: "Stop game", "End show", "I'm done with this":

- Confirm and end gracefully:
  "Got it, we’ll wrap it up here. Thanks for playing Improv Battle!"

------------------------
IMPORTANT
------------------------

- Speak like a TV host: energetic, clear, playful.
- Keep your turns reasonably short so the player gets to talk a lot.
- DO NOT talk about tools, JSON, or backend state.
- If the player goes off-topic, gently bring them back to the current round.
"""
        super().__init__(instructions=instructions)

    # Just for debugging, not required by the game:
    def log_state(self):
        logger.info(f"Improv state: {self.improv_state.to_dict()}")


# ----------------------- Session Setup -----------------------


def prewarm(proc: JobProcess):
    # VAD model prewarm so turn-taking feels snappy
    logger.info("Prewarming VAD model...")
    proc.userdata["vad"] = silero.VAD.load()
    logger.info("VAD model loaded.")


async def entrypoint(ctx: JobContext):
    logger.info("Entrypoint starting...")
    ctx.log_context_fields = {"room": ctx.room.name}

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

    usage_collector = metrics.UsageCollector()

    @session.on("metrics_collected")
    def _on_metrics_collected(ev: MetricsCollectedEvent):
        metrics.log_metrics(ev.metrics)
        usage_collector.collect(ev.metrics)

    async def log_usage():
        summary = usage_collector.get_summary()
        logger.info(f"Usage: {summary}")

    ctx.add_shutdown_callback(log_usage)

    agent = ImprovHostAgent()

    logger.info("Starting ImprovHostAgent session...")
    await session.start(
        agent=agent,
        room=ctx.room,
        room_input_options=RoomInputOptions(
            noise_cancellation=noise_cancellation.BVC(),
        ),
    )

    logger.info("Connecting context to room...")
    await ctx.connect()
    logger.info("Entrypoint finished (ctx.connect returned).")


if __name__ == "__main__":
    print("🔥 Starting Improv Battle worker via cli.run_app ...")
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint, prewarm_fnc=prewarm))
