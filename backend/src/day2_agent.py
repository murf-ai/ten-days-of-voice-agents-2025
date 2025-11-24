import logging
import json
import os
from datetime import datetime
from typing import Annotated, Literal
from dataclasses import dataclass, field

from dotenv import load_dotenv
from pydantic import Field
from livekit.agents import (
    Agent,
    AgentSession,
    JobContext,
    JobProcess,
    RunContext,
    MetricsCollectedEvent,
    WorkerOptions,
    RoomInputOptions,
    cli,
    function_tool,
    metrics,
)
from livekit.plugins import murf, silero, google, deepgram, noise_cancellation
from livekit.plugins.turn_detector.multilingual import MultilingualModel

# Load .env
load_dotenv(".env.local")

logger = logging.getLogger("agent")

# ======================================================
# ORDER STATE
# ======================================================

@dataclass
class OrderState:
    drinkType: str | None = None
    size: str | None = None
    milk: str | None = None
    extras: list[str] = field(default_factory=list)
    name: str | None = None

    def is_complete(self):
        return all([
            self.drinkType,
            self.size,
            self.milk,
            self.name
        ])

    def to_dict(self):
        return {
            "drinkType": self.drinkType,
            "size": self.size,
            "milk": self.milk,
            "extras": self.extras,
            "name": self.name
        }

@dataclass
class UserData:
    order: OrderState


# ======================================================
# JSON SAVE
# ======================================================

def get_orders_folder():
    base_dir = os.path.dirname(__file__)  # backend/src
    folder = os.path.join(base_dir, "orders")
    os.makedirs(folder, exist_ok=True)
    return folder


def save_order_to_json(order: OrderState):
    folder = get_orders_folder()

    filename = datetime.now().strftime("%Y%m%d_%H%M%S") + ".json"
    filepath = os.path.join(folder, filename)

    with open(filepath, "w") as f:
        json.dump(order.to_dict(), f, indent=4)

    print("\n✅ Order saved:", filepath)
    return filepath


# ======================================================
# TOOLS (FUNCTIONS)
# ======================================================

@function_tool
async def set_drink(
        ctx: RunContext[UserData],
        drink: Annotated[
            Literal["latte", "cappuccino", "americano", "espresso", "mocha"],
            Field(description="Type of coffee"),
        ],
):
    ctx.userdata.order.drinkType = drink
    return f"Great! A {drink}. What size would you like?"

@function_tool
async def set_size(
        ctx: RunContext[UserData],
        size: Annotated[
            Literal["small", "medium", "large"],
            Field(description="Drink size"),
        ],
):
    ctx.userdata.order.size = size
    return f"{size.title()} size. What milk would you like?"

@function_tool
async def set_milk(
        ctx: RunContext[UserData],
        milk: Annotated[
            Literal["whole", "skim", "soy", "almond", "oat"],
            Field(description="Milk type"),
        ],
):
    ctx.userdata.order.milk = milk
    return f"{milk.title()} milk. Any extras?"

@function_tool
async def set_extras(
        ctx: RunContext[UserData],
        extras: Annotated[
            list[Literal["caramel", "whipped cream", "extra shot", "sugar"]] | None,
            Field(description="Optional extras"),
        ] = None,
):
    ctx.userdata.order.extras = extras or []
    return "Great! And your name?"

@function_tool
async def set_name(
        ctx: RunContext[UserData],
        name: Annotated[str, Field(description="Customer name")],
):
    ctx.userdata.order.name = name.strip().title()
    return f"Thanks {ctx.userdata.order.name}! Finalizing your order."


@function_tool
async def complete_order(ctx: RunContext[UserData]):
    order = ctx.userdata.order

    if not order.is_complete():
        return "Some details are still missing."

    save_order_to_json(order)
    return f"Perfect! Your {order.size} {order.drinkType} with {order.milk} milk is ready to prepare!"


# ======================================================
# AGENT PERSONA
# ======================================================

class BaristaAgent(Agent):
    def __init__(self):
        super().__init__(
            instructions="""
You are a friendly barista at Gaza Coffee.
Take coffee orders step-by-step using the available tools.

Collect:
- drink type
- size
- milk
- extras
- name

When all info is ready, run complete_order().
Be fun, kind, and concise.
""",
            tools=[set_drink, set_size, set_milk, set_extras, set_name, complete_order]
        )


# ======================================================
# ENTRYPOINT
# ======================================================

def prewarm(proc: JobProcess):
    proc.userdata["vad"] = silero.VAD.load()


async def entrypoint(ctx: JobContext):
    userdata = UserData(order=OrderState())

    session = AgentSession(
        stt=deepgram.STT(model="nova-3"),
        llm=google.LLM(model="gemini-2.5-flash"),
        tts=murf.TTS(
            voice="en-US-matthew",
            style="Conversation",
            text_pacing=True,
        ),
        turn_detection=MultilingualModel(),
        vad=ctx.proc.userdata["vad"],
        userdata=userdata
    )

    usage_collector = metrics.UsageCollector()

    @session.on("metrics_collected")
    def collect(ev: MetricsCollectedEvent):
        usage_collector.collect(ev.metrics)

    await session.start(
        agent=BaristaAgent(),
        room=ctx.room,
        room_input_options=RoomInputOptions(
            noise_cancellation=noise_cancellation.BVC(),
        )
    )

    await ctx.connect()


# ======================================================
# RUN WORKER
# ======================================================

if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint, prewarm_fnc=prewarm))
