import os
import logging
import json
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
)
from livekit.agents.llm import ChatContext, ChatMessage
from livekit.plugins import murf, silero, google, deepgram, noise_cancellation
from livekit.plugins.turn_detector.multilingual import MultilingualModel

logger = logging.getLogger("WellnessAgent")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = os.path.join(BASE_DIR, "wellness_log.json")

load_dotenv(".env.local")


class WellnessAgent(Agent):
    def __init__(self):
        # --------- 1) LOAD HISTORY ---------
        history = self.load_history()
        if history:
            last = history[-1]
            history_text = (
                f"Last check-in summary: mood was '{last.get('mood', 'unknown')}', "
                f"energy was '{last.get('energy', 'unknown')}', "
                f"goals were {last.get('goals', [])}."
            )
        else:
            history_text = "No previous check-ins yet."

        # --------- 2) REAL INSTRUCTIONS (with history injected) ---------
        full_instructions = f"""
        You are a daily health and wellness companion.
        You speak through voice, so keep responses simple, natural, warm, and short.

        You already know this about the user from past check-ins:
        {history_text}

        Every session, follow this flow:

        1) Ask about mood and current energy.
           - Example: How are you feeling today? What’s your energy like?
           - If history shows low energy or stress, gently reference it:
             Example: Last time your energy was low. How does today compare?

        2) Ask if anything is stressing them out today.

        3) Ask for 1–3 goals or intentions for the day.
           - Both productivity (study, work, chores)
           - And self-care (rest, walk, hobbies)

        4) Offer small, actionable, NON-MEDICAL suggestions.
           - Break big goals into smaller steps
           - Suggest short breaks, 5–10 minute walks, stretching, deep breathing, etc.
           - Never diagnose or mention illnesses.

        5) End with a short recap:
           - Summarize their mood + energy
           - Repeat back the 1–3 goals
           - Ask: “Does this sound right?”

        Safety:
        - You are NOT a doctor or therapist.
        - Do NOT diagnose or prescribe treatments.
        """

        # ✅ IMPORTANT: pass the ACTUAL prompt, not the literal string
        super().__init__(instructions=full_instructions)

    # --------- JSON HELPERS ---------
    def load_history(self):
        if not os.path.exists(LOG_FILE):
            return []
        try:
            with open(LOG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data if isinstance(data, list) else []
        except Exception as e:
            logger.warning(f"Failed to load history: {e}")
            return []

    def save_entry(self, entry):
        history = self.load_history()
        history.append(entry)

        print("Saving JSON to:", LOG_FILE)
        print("Entry:", entry)

        os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
        with open(LOG_FILE, "w", encoding="utf-8") as f:
            json.dump(history, f, indent=4, ensure_ascii=False)

        print("Save Complete.")

    # --------- HOOKS CALLED BY LIVEKIT ---------
    async def on_enter(self):
        # Start the first question as soon as the agent joins the room
        await self.session.generate_reply()

    async def on_user_turn_completed(
        self,
        turn_ctx: ChatContext,
        new_message: ChatMessage,
    ) -> None:
        """
        This is called after the user finishes speaking and before the LLM reply is generated.
        We use it to roughly extract mood / energy / goals and save to JSON.
        """
        user_text = new_message.text_content or ""
        if not user_text.strip():
            return

        text = user_text.lower()

        mood = "unknown"
        energy = "unknown"
        goals: list[str] = []

        # ---- mood heuristics ----
        if "i feel" in text:
            mood = text.split("i feel", 1)[1].split(".")[0].strip()
        elif "feeling" in text:
            mood = text.split("feeling", 1)[1].split(".")[0].strip()
        elif any(w in text for w in ["tired", "exhausted", "drained"]):
            mood = "tired"
        elif "sick" in text:
            mood = "sick"

        # ---- energy heuristics ----
        if "energy" in text:
            energy = text.split("energy", 1)[1].split(".")[0].strip()
        elif any(w in text for w in ["very tired", "no energy", "drained", "low energy"]):
            energy = "low"
        elif any(w in text for w in ["energetic", "full of energy", "high energy"]):
            energy = "high"

        # ---- goals heuristics ----
        if any(
            k in text
            for k in ["goal", "goals", "today i want to", "i have to", "i need to", "i want to"]
        ):
            raw = text
            if "today i want to" in text:
                raw = text.split("today i want to", 1)[1]
            elif "i have to" in text:
                raw = text.split("i have to", 1)[1]
            elif "i need to" in text:
                raw = text.split("i need to", 1)[1]
            elif "i want to" in text:
                raw = text.split("i want to", 1)[1]
            elif "goals" in text:
                raw = text.split("goals", 1)[1]
            elif "goal" in text:
                raw = text.split("goal", 1)[1]

            goals = [
                g.strip()
                for g in raw.replace("and", ",").replace(".", "").split(",")
                if g.strip()
            ]

        entry = {
            "datetime": datetime.now().isoformat(),
            "mood": mood,
            "energy": energy,
            "goals": goals,
            "raw_user_message": user_text,
        }

        self.save_entry(entry)


def prewarm(proc: JobProcess):
    proc.userdata["vad"] = silero.VAD.load()


async def entrypoint(ctx: JobContext):
    ctx.log_context_fields = {
        "room": ctx.room.name,
    }

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

    await session.start(
        agent=WellnessAgent(),
        room=ctx.room,
        room_input_options=RoomInputOptions(
            noise_cancellation=noise_cancellation.BVC(),
        ),
    )

    await ctx.connect()


if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint, prewarm_fnc=prewarm))
