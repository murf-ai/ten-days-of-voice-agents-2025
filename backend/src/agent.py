import logging
import json
from typing import Annotated, Optional

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


logger = logging.getLogger("agent")
load_dotenv(".env.local")


# ------------------ ASSISTANT ------------------
class Assistant(Agent):
    def __init__(self) -> None:
        super().__init__(
            instructions="""
You are a professional barista at a premium specialty coffee shop.
You speak politely, confidently, and with clear product knowledge.
You ONLY talk about ordering, brewing, and serving coffee.
No AI talk. No breaking character. No emojis or special formatting.
Keep responses short, friendly, and direct.
Always reconfirm before submitting for ordering complete for each like before drink type then size then milk then name 
CORE MISSION
Take the customer’s coffee order by collecting these REQUIRED details:
1) Drink Type — latte, espresso, cold brew, cappuccino
   (If they request something else, politely explain it’s unavailable and guide them to the nearest option.)
2) Size — Small (8 oz), Medium (12 oz), Large (16 oz)
3) Milk Choice — whole, skim, 2 percent, oat, almond, soy, coconut, lactose free
(Ask them for extras Extras are optional:
extra shot, vanilla syrup, caramel syrup, hazelnut syrup, mocha syrup, whipped cream, sugar, honey, stevia, hot or iced)
4) Customer Name


ORDER-TAKING RULES
• Ask ONLY for missing information.
• Do NOT repeat information the customer already gave.
• Gather one detail at a time and guide the customer smoothly.
• Suggest extras politely but never pressure the customer.
• Match the customer's tone and pace:
  - Casual → casual
  - Formal → professional
  - Non-native speaker → simple words
  - Tech-savvy → respond with light technical analogies if appropriate

TOOL CALL RULES (update_order)
• Every time the customer provides ANY new order detail, you MUST call update_order.
• The tool call must include ONLY the information the customer just provided.
• During a tool call, do NOT speak normally — output only the tool call.
• After the tool call response returns, continue talking normally and ask for the next missing detail.

WHEN ORDER IS COMPLETE
Once you have Drink Type + Size + Milk Choice + Customer Name:
• Confirm the complete order warmly and professionally.
• Stop asking for more information.
• Remain a barista in character for the rest of the conversation.

CONVERSATION START
Begin by asking which drink the customer would like and list the drink options clearly.

""",
        )

        self.order_state = {
            "drinkType": "",
            "size": "",
            "milk": "",
            "extras": [],
            "name": "",
        }

    @function_tool
    async def update_order(
        self,
        # We use Optional[str] so the AI can send 'null' without crashing the app
        drinkType: Annotated[Optional[str], "latte, espresso, cold brew, cappuccino"] = None,
        size: Annotated[Optional[str], "Small, Medium, Large"] = None,
        milk: Annotated[Optional[str], "Whole, Oat, Almond"] = None,
        extras: Annotated[Optional[str], "syrups, sugar, etc"] = None,
        name: Annotated[Optional[str], "Customer Name"] = None,
    ):
        """Updates order state and saves to JSON immediately."""
        
        # 1. Update State (Only if value is not None)
        if drinkType: self.order_state["drinkType"] = drinkType
        if size: self.order_state["size"] = size
        if milk: self.order_state["milk"] = milk
        if name: self.order_state["name"] = name

        if extras:
            if extras.lower() in ["no", "none", "nothing"]:
                self.order_state["extras"] = []
            elif extras not in self.order_state["extras"]:
                self.order_state["extras"].append(extras)

        # 2. Calculate Missing Fields (Check for empty strings)
        missing = [k for k, v in self.order_state.items() if k != "extras" and not v]

        # 3. LIVE SAVE 
        with open("order_summary.json", "w") as f:
            json.dump(self.order_state, f, indent=2)
        
        logger.info(f"State Updated: {self.order_state}")

        if not missing:
            return "Order is complete and saved to file. Confirm the full details to the customer."

        return f"Order updated. Still missing: {', '.join(missing)}."

# ------------------ PREWARM ------------------
def prewarm(proc: JobProcess):
    proc.userdata["vad"] = silero.VAD.load()


# ------------------ ENTRYPOINT ------------------
async def entrypoint(ctx: JobContext):
    ctx.log_context_fields = {"room": ctx.room.name}

    session = AgentSession(
        stt=deepgram.STT(model="nova-3"),
        llm=google.LLM(model="gemini-2.0-flash"),
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
    def _on_metrics(ev: MetricsCollectedEvent):
        metrics.log_metrics(ev.metrics)
        usage_collector.collect(ev.metrics)

    async def log_usage():
        logger.info(f"Usage: {usage_collector.get_summary()}")

    ctx.add_shutdown_callback(log_usage)

    await session.start(
        agent=Assistant(),
        room=ctx.room,
        room_input_options=RoomInputOptions(
            noise_cancellation=noise_cancellation.BVC(),
        ),
    )

    await ctx.connect()


# ------------------ WORKER ------------------
if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint, prewarm_fnc=prewarm))