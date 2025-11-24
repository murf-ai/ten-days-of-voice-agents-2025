import logging
import json
import os
from datetime import datetime

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

load_dotenv(".env.local")


class Assistant(Agent):
    def __init__(self, history_note: str = "") -> None:
        # Base system prompt
        base_instructions = """
You are a warm, supportive, realistic Health & Wellness voice companion.
Every day, you check in with the user about their mood and goals.

Conversation flow:
1. Ask about mood and energy.
   Examples: "How are you feeling today?", "What's your energy like?", "Anything stressing you out right now?"
2. Ask about their intentions / goals for today.
   Examples: "What are 1–3 things you'd like to get done today?", "Is there anything you want to do for yourself (rest, exercise, hobbies)?"
3. Provide supportive reflection and simple advice.
   Keep suggestions small and realistic (rest, a short walk, breaks, focus on one task at a time).
4. End with a short recap:
   - Mood summary
   - 1–3 goals
   - Ask: "Does this sound right?"

VERY IMPORTANT:
- You are not a doctor and cannot diagnose or treat anything.
- Avoid medical claims or diagnoses.
- Do not mention JSON, files, logs, tools, or code to the user.
- After you understand today's mood, energy, and goals, call the `log_checkin` tool ONCE to store the results.

If past check-in history exists, reference it naturally:
Examples:
- "Last time you said your energy was low — how does today compare?"
- "Previously you wanted to focus on deep work — how did that go?"

Be non-judgmental, encouraging, and gentle. Keep responses short and conversational.
"""

        # If we have any history note from JSON, append it as context
        if history_note:
            base_instructions += f"""

Additional context from previous check-ins (do NOT read this directly to the user, just use it for memory):
{history_note}

Use this context to ask gentle follow-up questions like:
- "Last time you mentioned: {history_note}. How are things today compared to then?"
Remember: never say that you are reading from a file.
"""

        super().__init__(instructions=base_instructions)

    # ------------- Wellness JSON Logging Tool (used by the LLM) -------------
    @function_tool
    async def log_checkin(
        self,
        context: RunContext,
        mood: str,
        energy: str,
        goals: list,
    ) -> str:
        """
        Store the user's check-in in wellness_log.json and return a short recap string.

        Args:
            mood: user-described mood (e.g. "anxious but hopeful")
            energy: user-described energy level (e.g. "low", "medium", "high")
            goals: list of 1–3 goals/intentions for today
        """
        log_file = "wellness_log.json"

        entry = {
            "timestamp": datetime.now().isoformat(),
            "mood": mood,
            "energy": energy,
            "goals": goals,
            "summary": f"Mood: {mood}, energy: {energy}, goals: {', '.join(goals)}",
        }

        # Load existing data if file exists
        try:
            with open(log_file, "r", encoding="utf-8") as f:
                data = json.load(f)
        except FileNotFoundError:
            data = []
        except json.JSONDecodeError:
            data = []

        data.append(entry)

        # Write back to JSON
        with open(log_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        logger.info(
            f"Logged wellness check-in: mood={mood}, energy={energy}, goals={goals}"
        )

        # This text is what the LLM can speak back to user
        return (
            f"Thanks for sharing. I’ve logged that you’re feeling {mood} with {energy} energy, "
            f"and today’s goals are: {', '.join(goals)}. Let’s keep it simple and kind to yourself today."
        )


# ----------------------- Session Setup -----------------------
def prewarm(proc: JobProcess):
    proc.userdata["vad"] = silero.VAD.load()


async def entrypoint(ctx: JobContext):
    ctx.log_context_fields = {"room": ctx.room.name}

    # ---------- Read JSON history (if any) to pass as context ----------
    history_note = ""
    log_file = "wellness_log.json"
    if os.path.exists(log_file):
        try:
            with open(log_file, "r", encoding="utf-8") as f:
                past = json.load(f)
                if isinstance(past, list) and len(past) > 0:
                    last = past[-1]
                    mood = last.get("mood", "unknown")
                    energy = last.get("energy", "unknown")
                    goals = last.get("goals", [])
                    goals_str = ", ".join(goals) if goals else "no goals recorded"

                    history_note = (
                        f"Last check-in: mood='{mood}', energy='{energy}', "
                        f"goals were: {goals_str}."
                    )
        except Exception as e:
            logger.warning(f"Failed to read wellness_log.json: {e}")
            history_note = ""

    # ---------- Voice AI pipeline ----------
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

    # Start the session with our wellness Assistant, passing history
    await session.start(
        agent=Assistant(history_note=history_note),
        room=ctx.room,
        room_input_options=RoomInputOptions(
            noise_cancellation=noise_cancellation.BVC(),
        ),
    )

    await ctx.connect()


if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint, prewarm_fnc=prewarm))
