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
    function_tool,
    RunContext
)
from livekit.plugins import murf, silero, google, deepgram, noise_cancellation
from livekit.plugins.turn_detector.multilingual import MultilingualModel
import os 
import json
from datetime import datetime

logger = logging.getLogger("agent")

load_dotenv(".env.local")




class CofeeBaristaAssistant(Agent):
    def __init__(self) -> None:
        super().__init__(
            instructions="""You are a friendly and knowledgeable barista at Blue Tokai Coffee, India's finest specialty coffee roaster. 
                            The user is interacting with you via voice, even if you perceive the conversation as text.

                            Your role is to help customers place their coffee orders in a warm, conversational manner.

                            When taking an order, you need to collect:
                            1. Drink type (cappuccino, latte, espresso, cold brew, filter coffee, etc.)
                            2. Size (small, medium, large)
                            3. Milk preference (whole milk, oat milk, almond milk, soy milk, or no milk)
                            4. Any extras (extra shot, vanilla syrup, caramel, whipped cream, etc.)
                            5. Customer's name for the order

                            Ask one question at a time in a natural, friendly way. Don't overwhelm the customer with all questions at once.
                            Once you have all the information, confirm the complete order with the customer before finalizing.

                            Your responses should be:
                            - Warm and welcoming like a real barista
                            - Concise and conversational
                            - Free of complex formatting, emojis, or special characters
                            - Knowledgeable about Blue Tokai's coffee offerings

                            Remember, you're representing Blue Tokai's commitment to quality and great customer service!""",
        )
        
        #Initialize oreder state
        self.order_state = {
            "drinkType": None,
            "size": None,
            "milk": None,
            "extras": [],
            "name": None
}

    # To add tools, use the @function_tool decorator.
    # Here's an example that adds a simple weather tool.
    # You also have to add `from livekit.agents import function_tool, RunContext` to the top of this file
    @function_tool
    async def finalize_order(
        self, 
        context: RunContext,      
        drink_type: str,
        size: str,
        milk: str,
        extras: list,
        name: str
    ):
        """Finalizes and saves the customer's coffee order to a JSON file and sends it to the frontend.
        Call this function only after confirming all order details with the customer.
        
        Args:
            drink_type: The type of coffee drink (e.g., cappuccino, latte, espresso)
            size: The size of the drink (small, medium, or large)
            milk: The milk preference (whole milk, oat milk, almond milk, soy milk, or no milk)
            extras: List of any additional items (e.g., extra shot, vanilla syrup, caramel)
            name: The customer's name for the order
        """
         
        #update the order_state
        self.order_state = {
            "drinkType": drink_type,
            "size": size,
            "milk": milk,
            "extras": extras if extras else [],
            "name": name
        }
        
        
        
        #create order directory if it doesn't exist
        os.makedirs("orders", exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"orders/order_{timestamp}_{name.replace(' ', '_')}.json"
        
        #save order to json file
        try:
            with open(filename, "w") as f:
                json.dump(self.order_state, f, indent=2)
            
            logger.info(f"Order saved successfully: {filename}")
            logger.info(f"Order details: {json.dumps(self.order_state, indent=2)}")
            
            
               
            
            return f"Perfect! Your order has been placed, {name}. One {size} {drink_type} with {milk}{' and ' + ', '.join(extras) if extras else ''} coming right up! Your order number is {timestamp[-6:]}. It'll be ready in just a few minutes."
        
        except Exception as e:
            logger.error(f"Error saving order: {str(e)}")
            return "I apologize, there was an issue saving your order. Let me get that fixed for you right away."
        
   
    async def send_order_to_frontend(
       self, 
       context: RunContext,    
       order_data: dict):
        
       """Send the order data to the frontend via text stream."""     
       try:
           #get the room from context 
           print("context", context)
           await context.room.local_participant.send_text(
               json.dumps(order_data),
               topic="coffee-order"
           )
           logger.info(f"Order sent to frontend: {order_data}")
        
       except Exception as e:
           logger.error(f"Error sending order data to frontend: str{e}")
        


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
        agent=CofeeBaristaAssistant(),
        room=ctx.room,
        room_input_options=RoomInputOptions(
            # For telephony applications, use `BVCTelephony` for best results
            noise_cancellation=noise_cancellation.BVC(),
        ),
    )
    await session.say(
    "HELLO, welcome to BLUE TOKAI Coffee Barista, India's finest specialty coffee roaster.",
    allow_interruptions=False,
)

    # Join the room and connect to the user
    await ctx.connect()


if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint, prewarm_fnc=prewarm))
