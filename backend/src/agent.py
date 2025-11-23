import logging
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

logger = logging.getLogger("agent")

load_dotenv(".env.local")


class MurfBrew(Agent):

    def __init__(self):
        super().__init__(
            instructions="""
You are MurfBrew, a friendly and confident AI barista from a premium café.
The user speaks to you through voice.  

Your job:
- Greet the customer naturally.
- Take their coffee order step by step.
- Ask one question at a time in this order: drink → size → hot/iced → milk → extras → confirmation.
- Remember what they answered.
- Once the order is fully known, repeat it naturally and ask if you'd like to confirm.
- If confirmed, close the interaction politely and confidently.

Tone rules:
- Sound like a real barista, not an AI assistant.
- Keep responses short, casual and natural.
- No emojis. No robotic phrases.    
""",
        )

        # state memory for the order
        self.state = {
            "drink": None,
            "size": None,
            "temperature": None,
            "milk": None,
            "extras": [],
            "confirmed": False,
        }

    async def on_user_message(self, ctx: AgentSession, message: str):
        msg = message.lower().strip()

        # Step 1: drink
        if self.state["drink"] is None:
            self.state["drink"] = msg
            return await ctx.send_message("Nice choice. What size would you like? Small, medium, or large?")

        # Step 2: size
        if self.state["size"] is None:
            self.state["size"] = msg
            return await ctx.send_message("Got it. Would you like it hot or iced?")

        # Step 3: temperature
        if self.state["temperature"] is None:
            self.state["temperature"] = msg
            return await ctx.send_message("What milk do you want? Whole, skim, oat or almond?")

        # Step 4: milk
        if self.state["milk"] is None:
            self.state["milk"] = msg
            return await ctx.send_message("Any extras? Sugar, whipped cream, caramel, chocolate or extra espresso shot?")

        # Step 5: extras (collect once, then confirm)
        if not self.state["confirmed"]:
            if msg not in ["no", "none", "that's all", "done"]:
                self.state["extras"].append(msg)

            self.state["confirmed"] = True

            summary = f"Alright, so you ordered a {self.state['size']} {self.state['temperature']} {self.state['drink']} with {self.state['milk']} milk"
            if self.state["extras"]:
                summary += f" and extras: {', '.join(self.state['extras'])}."

            return await ctx.send_message(summary + " Should I confirm the order?")

        # Final confirmation
        if "yes" in msg or "confirm" in msg:
            return await ctx.send_message("Perfect. Your drink is being prepared. Thanks for choosing MurfBrew.")

        return await ctx.send_message("No problem. Would you like to change something or restart?")


def prewarm(proc: JobProcess):
    proc.userdata["vad"] = silero.VAD.load()


async def entrypoint(ctx: JobContext):

    ctx.log_context_fields = { "room": ctx.room.name }

    session = AgentSession(
        stt=deepgram.STT(model="nova-3"),
        llm=google.LLM(model="gemini-2.5-flash"),
        tts=murf.TTS(
            voice="en-US-matthew",
            style="Conversation",
            tokenizer=tokenize.basic.SentenceTokenizer(min_sentence_len=2),
            text_pacing=True
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
        agent=MurfBrew(),
        room=ctx.room,
        room_input_options=RoomInputOptions(
            noise_cancellation=noise_cancellation.BVC(),
        ),
    )

    await ctx.connect()


if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint, prewarm_fnc=prewarm))
