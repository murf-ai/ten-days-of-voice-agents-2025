import logging
import json
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

from livekit.plugins import murf,silero,google,deepgram,noise_cancellation
from livekit.plugins.turn_detector.multilingual import MultilingualModel

logger = logging.getLogger("coffeeAgent")

load_dotenv(".env.local")


class CoffeeAgent(Agent):
    def __init__(self):
        super().__init__(
            instructions="""
            You are a friendly barista at Coffee Haven.

            You maintain an order object:

            {
              "drinkType": "",
              "size": "",
              "milk": "",
              "extras": [],
              "name": ""
            }

            Ask questions to fill all fields.
            Once the order is complete, save it to a JSON file.
            """
        )

        self.order = {
            "drinkType": "",
            "size": "",
            "milk": "",
            "extras": [],
            "name": ""
        }

    # Helper: check if order is complete
    def order_complete(self):
        return all([
            self.order["drinkType"],
            self.order["size"],
            self.order["milk"],
            self.order["name"]
        ])

    # Handle user messages
    async def on_message(self, msg, ctx):
        user_input = msg.text.strip().lower()

        if not self.order["name"]:
            self.order["name"] = msg.text
            await ctx.send_message(f"Hi {self.order['name']}! What drink would you like?")
            return

        if not self.order["drinkType"]:
            self.order["drinkType"] = msg.text
            await ctx.send_message("What size would you like? Small, medium, or large?")
            return

        if not self.order["size"]:
            self.order["size"] = msg.text
            await ctx.send_message("What milk would you like? Regular, oat, soy, almond, or none?")
            return

        if not self.order["milk"]:
            self.order["milk"] = msg.text
            await ctx.send_message("Any extras? Say 'no' if none.")
            return

        if user_input != "no":
            self.order["extras"].append(msg.text)

        if self.order_complete():
            await self.finish_order(ctx)
        else:
            await ctx.send_message("Anything else? Or say 'no' to finish.")

    async def finish_order(self, ctx):
        summary = (
            f"Here's your order summary:\n"
            f"Name: {self.order['name']}\n"
            f"Drink: {self.order['drinkType']}\n"
            f"Size: {self.order['size']}\n"
            f"Milk: {self.order['milk']}\n"
            f"Extras: {', '.join(self.order['extras']) if self.order['extras'] else 'None'}"
        )

        await ctx.send_message(summary)

        filename = f"{self.order['name']}_order.json"
        with open(filename, "w") as f:
            json.dump(self.order, f, indent=4)

        await ctx.send_message("Your order has been saved. Thanks for visiting Coffee Haven!")

            
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

    # Start the session, which initializes the voice pipeline and warms up the models
    await session.start(
        agent=CoffeeAgent(),
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

                