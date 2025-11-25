import logging
import os
import json
from datetime import datetime
from typing import List, Optional

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


@function_tool
async def save_wellness(
    ctx: RunContext,
    mood: str,
    energy: str,
    objectives: List[str],
    notes: Optional[str] = None,
) -> str:
    """Save a wellness check-in to `wellness_log.json` and return a short confirmation.

    Schema (one entry):
    {
      "timestamp": "ISO string",
      "mood": "user text",
      "energy": "user text or scale",
      "objectives": ["1..3 objectives"],
      "notes": "optional agent summary"
    }
    """

    entry = {
        "timestamp": datetime.utcnow().isoformat(timespec="seconds"),
        "mood": mood,
        "energy": energy,
        "objectives": objectives or [],
        "notes": notes or "",
    }

    # Place file next to the backend folder (one level up from this file)
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    path = os.path.join(base_dir, "wellness_log.json")
    # Ensure file exists and is a JSON array
    try:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f) or []
        else:
            data = []
    except Exception:
        data = []

    data.append(entry)

    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    return f"saved:{path}"


@function_tool
async def find_faq(ctx: RunContext, query: str) -> str:
    """Find a best-effort FAQ answer from `company_data.json`.

    This is a simple keyword-match search over FAQ entries. Returns the
    matched answer or a fallback indicating no answer found.
    """
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    data_path = os.path.join(base_dir, "company_data.json")
    try:
        with open(data_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return "Sorry, I can't find the company FAQ right now."

    faqs = data.get("faq", [])
    q = (query or "").lower()
    best = None
    best_score = 0
    for entry in faqs:
        text = (entry.get("question", "") + " " + entry.get("answer", "")).lower()
        # simple score: count of query words present
        score = sum(1 for w in q.split() if w and w in text)
        if score > best_score:
            best_score = score
            best = entry

    if best and best_score > 0:
        return f"FAQ: {best.get('question')}\nAnswer: {best.get('answer')}"
    # fallback: if there's a short product summary, return that for general questions
    summary = data.get("summary")
    if summary and any(w in summary.lower() for w in q.split()):
        return f"{summary}"

    return "I don't have a direct answer in the FAQ for that — would you like me to connect you with a specialist or leave a message?"


@function_tool
async def save_lead(
    ctx: RunContext,
    name: Optional[str] = None,
    company: Optional[str] = None,
    email: Optional[str] = None,
    role: Optional[str] = None,
    use_case: Optional[str] = None,
    team_size: Optional[str] = None,
    timeline: Optional[str] = None,
    notes: Optional[str] = None,
) -> str:
    """Persist a lead as JSON in `leads.json` and return confirmation path."""

    entry = {
        "timestamp": datetime.utcnow().isoformat(timespec="seconds"),
        "name": name or "",
        "company": company or "",
        "email": email or "",
        "role": role or "",
        "use_case": use_case or "",
        "team_size": team_size or "",
        "timeline": timeline or "",
        "notes": notes or "",
    }

    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    path = os.path.join(base_dir, "leads.json")
    try:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f) or []
        else:
            data = []
    except Exception:
        data = []

    data.append(entry)

    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    return f"saved:{path}"


class Assistant(Agent):
    def __init__(self, previous_entry: Optional[dict] = None) -> None:
        # Wellness-focused companion: daily check-ins, non-diagnostic support
        prev_note = ""
        if previous_entry:
            prev_ts = previous_entry.get("timestamp")
            prev_mood = previous_entry.get("mood")
            prev_energy = previous_entry.get("energy")
            prev_obj = ", ".join(previous_entry.get("objectives", []))
            prev_note = (
                f"Last time ({prev_ts}) you said your mood was '{prev_mood}' and energy was '{prev_energy}'. "
                f"You were focusing on: {prev_obj}."
            )

        instructions = (
            "You are a calm, grounded, and supportive health & wellness companion. "
            "You are NOT a clinician and must not provide medical advice or diagnosis. "
            "Your role is to do a short daily check-in: ask about mood, energy, and any stressors; "
            "ask for 1–3 practical objectives for the day; offer short, realistic, non-medical suggestions; "
            "and close with a concise recap and confirmation. "
            "Keep suggestions small and actionable (e.g., take a 5-minute walk, break tasks into steps, drink water, take short breaks). "
            "When the user confirms goals, persist the check-in by calling the tool"
            " `save_wellness(mood, energy, objectives, notes)` with a brief agent summary sentence. "
            "Always politely refuse harmful or unsafe requests. "
        )

        # If a previous entry exists, include a brief reference that the agent can use
        if prev_note:
            instructions = prev_note + " " + instructions

        super().__init__(instructions=instructions, tools=[save_wellness])



class SDRAgent(Agent):
    def __init__(self) -> None:
        # Load a short company summary if available and craft SDR instructions
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        data_path = os.path.join(base_dir, "company_data.json")
        summary = ""
        try:
            with open(data_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                summary = data.get("summary", "")
        except Exception:
            summary = ""

        instructions = (
            "You are a friendly, professional Sales Development Representative (SDR) for the company described in the provided company data. "
            "Greet visitors warmly, ask what brought them here, and focus the conversation on understanding their needs. "
            "Use the FAQ tool when asked product/company/pricing questions, and do not invent details not present in the FAQ or company content. "
            "Collect lead information naturally during the conversation: name, company, email, role, use case, team size, and timeline. "
            "When the user indicates they are done (e.g., 'That's all', 'Thanks', 'I'm done'), summarize the lead concisely and persist the lead by calling the tool `save_lead(...)`. "
        )

        if summary:
            instructions = f"Company summary: {summary}\n" + instructions

        super().__init__(instructions=instructions, tools=[find_faq, save_lead])

    # To add tools, use the @function_tool decorator.
    # Here's an example that adds a simple weather tool.
    # You also have to add `from livekit.agents import function_tool, RunContext` to the top of this file
    # @function_tool
    # async def lookup_weather(self, context: RunContext, location: str):
    #     """Use this tool to look up current weather information in the given location.
    #
    #     If the location is not supported by the weather service, the tool will indicate this. You must tell the user the location's weather is unavailable.
    #
    #     Args:
    #         location: The location to look up weather information for (e.g. city name)
    #     """
    #
    #     logger.info(f"Looking up weather for {location}")
    #
    #     return "sunny with a temperature of 70 degrees."


def prewarm(proc: JobProcess):
    proc.userdata["vad"] = silero.VAD.load()


async def entrypoint(ctx: JobContext):
    # Logging setup
    # Add any other context you want in all log entries here
    ctx.log_context_fields = {
        "room": ctx.room.name,
    }

    # Set up a voice AI pipeline using OpenAI, Cartesia, AssemblyAI, and the LiveKit turn detector
    session = AgentSession(
        # Speech-to-text (STT) is your agent's ears, turning the user's speech into text that the LLM can understand
        # See all available models at https://docs.livekit.io/agents/models/stt/
        stt=deepgram.STT(model="nova-3"),
        # A Large Language Model (LLM) is your agent's brain, processing user input and generating a response
        # See all available models at https://docs.livekit.io/agents/models/llm/
        llm=google.LLM(
                model="gemini-2.5-flash",
            ),
        # Text-to-speech (TTS) is your agent's voice, turning the LLM's text into speech that the user can hear
        # See all available models as well as voice selections at https://docs.livekit.io/agents/models/tts/
        tts=murf.TTS(
                voice="en-US-matthew", 
                style="Conversation",
                tokenizer=tokenize.basic.SentenceTokenizer(min_sentence_len=2),
                text_pacing=True
            ),
        # VAD and turn detection are used to determine when the user is speaking and when the agent should respond
        # See more at https://docs.livekit.io/agents/build/turns
        turn_detection=MultilingualModel(),
        vad=ctx.proc.userdata["vad"],
        # allow the LLM to generate a response while waiting for the end of turn
        # See more at https://docs.livekit.io/agents/build/audio/#preemptive-generation
        preemptive_generation=True,
    )

    # To use a realtime model instead of a voice pipeline, use the following session setup instead.
    # (Note: This is for the OpenAI Realtime API. For other providers, see https://docs.livekit.io/agents/models/realtime/))
    # 1. Install livekit-agents[openai]
    # 2. Set OPENAI_API_KEY in .env.local
    # 3. Add `from livekit.plugins import openai` to the top of this file
    # 4. Use the following session setup instead of the version above
    # session = AgentSession(
    #     llm=openai.realtime.RealtimeModel(voice="marin")
    # )

    # Metrics collection, to measure pipeline performance
    # For more information, see https://docs.livekit.io/agents/build/metrics/
    usage_collector = metrics.UsageCollector()

    @session.on("metrics_collected")
    def _on_metrics_collected(ev: MetricsCollectedEvent):
        metrics.log_metrics(ev.metrics)
        usage_collector.collect(ev.metrics)

    async def log_usage():
        summary = usage_collector.get_summary()
        logger.info(f"Usage: {summary}")

    ctx.add_shutdown_callback(log_usage)

    # # Add a virtual avatar to the session, if desired
    # # For other providers, see https://docs.livekit.io/agents/models/avatar/
    # avatar = hedra.AvatarSession(
    #   avatar_id="...",  # See https://docs.livekit.io/agents/models/avatar/plugins/hedra
    # )
    # # Start the avatar and wait for it to join
    # await avatar.start(session, room=ctx.room)

    # Before starting, read the wellness log and pass the most recent entry to the Assistant
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    wellness_path = os.path.join(base_dir, "wellness_log.json")
    last_entry = None
    try:
        if os.path.exists(wellness_path):
            with open(wellness_path, "r", encoding="utf-8") as f:
                data = json.load(f) or []
                if isinstance(data, list) and data:
                    last_entry = data[-1]
    except Exception:
        last_entry = None

    # Start the session, which initializes the voice pipeline and warms up the models
    # Use the SDR agent persona so the assistant behaves like an SDR for the chosen company
    await session.start(
        agent=SDRAgent(),
        room=ctx.room,
        room_input_options=RoomInputOptions(
            # For telephony applications, use `BVCTelephony` for best results
            noise_cancellation=noise_cancellation.BVC(),
        ),
    )

    # Join the room and connect to the user
    await ctx.connect()


if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint, prewarm_fnc=prewarm))
