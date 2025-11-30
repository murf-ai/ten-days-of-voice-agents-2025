import logging
import json
from pathlib import Path
from datetime import datetime
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
    function_tool,
    RunContext,
)
from livekit.plugins import murf, silero, google, deepgram, noise_cancellation
from livekit.plugins.turn_detector.multilingual import MultilingualModel

logger = logging.getLogger("agent")

load_dotenv(".env.local")

# ------------ SIMPLE BUILT-IN CATALOG (NO FILE NEEDED) ------------

CATALOG: List[Dict[str, Any]] = [
    {
        "id": "mug-001",
        "name": "Stoneware Coffee Mug",
        "description": "A sturdy stoneware mug for hot coffee or tea.",
        "price": 799,
        "currency": "INR",
        "category": "mug",
        "color": "white",
        "sizes": [],
        "tags": ["coffee", "mug", "ceramic"],
    },
    {
        "id": "mug-002",
        "name": "Matte Black Mug",
        "description": "Matte black ceramic mug with a minimal FalconStore logo.",
        "price": 899,
        "currency": "INR",
        "category": "mug",
        "color": "black",
        "sizes": [],
        "tags": ["coffee", "mug", "black", "minimal"],
    },
    {
        "id": "hoodie-001",
        "name": "Cozy Black Hoodie",
        "description": "Fleece-lined hoodie for everyday comfort.",
        "price": 1299,
        "currency": "INR",
        "category": "hoodie",
        "color": "black",
        "sizes": ["S", "M", "L", "XL"],
        "tags": ["hoodie", "black", "winter"],
    },
    {
        "id": "hoodie-002",
        "name": "Blue Oversized Hoodie",
        "description": "Oversized hoodie in deep blue with front pocket.",
        "price": 1499,
        "currency": "INR",
        "category": "hoodie",
        "color": "blue",
        "sizes": ["M", "L"],
        "tags": ["hoodie", "blue", "oversized"],
    },
    {
        "id": "tee-001",
        "name": "Falcon Classic T-Shirt",
        "description": "Soft cotton unisex t-shirt with small chest logo.",
        "price": 699,
        "currency": "INR",
        "category": "tshirt",
        "color": "black",
        "sizes": ["S", "M", "L", "XL"],
        "tags": ["tshirt", "black", "casual"],
    },
]


# ------------ ORDERS JSON HELPERS ------------


def load_orders() -> List[Dict[str, Any]]:
    base_dir = Path(__file__).resolve().parent.parent
    path = base_dir / "orders" / "day9_orders.json"
    if not path.exists():
        return []
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, list):
                return data
    except Exception as e:
        logger.warning(f"Failed to load day9_orders.json: {e}")
    return []


def save_orders(orders: List[Dict[str, Any]]) -> None:
    base_dir = Path(__file__).resolve().parent.parent
    orders_dir = base_dir / "orders"
    orders_dir.mkdir(parents=True, exist_ok=True)
    path = orders_dir / "day9_orders.json"
    with path.open("w", encoding="utf-8") as f:
        json.dump(orders, f, indent=2, ensure_ascii=False)


# ------------ AGENT ------------


class FalconStoreAgent(Agent):
    """
    Very simple ACP-inspired e-commerce voice agent.

    - Conversation handled by LLM.
    - Commerce handled by tools:
        * create_order_from_text
        * get_last_order_summary
    """

    def __init__(self) -> None:
        self.catalog = CATALOG
        self.brand_name = "FalconStore"

        instructions = f"""
You are a friendly e-commerce voice assistant for {self.brand_name},
a fictional Indian online store that sells mugs, hoodies and t-shirts.

HIGH-LEVEL BEHAVIOR
- Greet the user and explain you can help them browse products and place orders.
- When they describe what they want to BUY, you MUST call the tool
  `create_order_from_text` with their request text.
- After the tool returns, speak out the confirmation naturally.
- When they ask "What did I just buy?" or "last order", you MUST call
  `get_last_order_summary` and read it back.

CATALOG (examples you can mention)
- Cozy Black Hoodie (hoodie-001), black, ₹1299, sizes S–XL
- Blue Oversized Hoodie (hoodie-002), blue, ₹1499
- Falcon Classic T-Shirt (tee-001), black tee, ₹699
- Matte Black Mug (mug-002), black mug, ₹899
- Stoneware Coffee Mug (mug-001), white mug, ₹799

WHEN TO CALL TOOLS
- If user says anything like:
    "I want to buy a black hoodie in size M"
    "Order the black hoodie you mentioned"
    "Get me that matte black mug"
  → Call `create_order_from_text` with the entire user sentence
    as the `request` argument. Do not guess totals yourself.

- If user says:
    "What did I just buy?"
    "Tell me my last order"
  → Call `get_last_order_summary`.

RULES
- Use only INR prices.
- Do not invent products outside the catalog; pick the closest match.
- Keep responses short and natural.
- Do not mention tools or JSON to the user.
"""
        super().__init__(instructions=instructions)

    # ---------- Internal helpers ----------

    def _match_product_from_text(self, text: str) -> Dict[str, Any]:
        """
        Very naive matching: look for keywords like 'hoodie', 't-shirt', 'mug'
        and colors like 'black', 'blue', etc. Pick the first product that matches.
        """
        t = text.lower()
        category = None
        if "hoodie" in t:
            category = "hoodie"
        elif "t-shirt" in t or "tshirt" in t or "tee" in t:
            category = "tshirt"
        elif "mug" in t:
            category = "mug"

        color = None
        for c in ["black", "blue", "white"]:
            if c in t:
                color = c
                break

        # basic scan over catalog
        candidates = []
        for p in self.catalog:
            if category and p.get("category") != category:
                continue
            if color and p.get("color") != color:
                continue
            candidates.append(p)

        if candidates:
            return candidates[0]

        # fallback: any item from correct category
        if category:
            for p in self.catalog:
                if p.get("category") == category:
                    return p

        # final fallback: just first product
        return self.catalog[0]

    def _extract_quantity(self, text: str) -> int:
        t = text.lower().split()
        for w in t:
            digits = "".join(ch for ch in w if ch.isdigit())
            if digits:
                try:
                    q = int(digits)
                    if q > 0:
                        return q
                except ValueError:
                    continue
        return 1

    def _extract_size(self, text: str) -> Optional[str]:
        t = text.upper()
        for size in ["XS", "S", "M", "L", "XL", "XXL"]:
            if f" {size} " in f" {t} ":
                return size
        return None

    # ---------- TOOLS ----------

    @function_tool()
    async def create_order_from_text(
        self,
        context: RunContext,
        request: str,
    ) -> str:
        """
        Create an order based on a natural language request.

        Args:
            request: What the user said, like
                "I want to buy a black hoodie in size M"
                or "Order two matte black mugs".
        """
        req = request.strip()
        if not req:
            return "I couldn't understand the order request."

        product = self._match_product_from_text(req)
        quantity = self._extract_quantity(req)
        size = self._extract_size(req)

        # if product supports sizes but none found, default to first size
        sizes = product.get("sizes") or []
        chosen_size = None
        if sizes:
            if size and size in sizes:
                chosen_size = size
            else:
                chosen_size = sizes[0]

        unit_price = product["price"]
        currency = product.get("currency", "INR")
        line_total = unit_price * quantity

        orders = load_orders()
        order_id = f"ORD-{len(orders) + 1:04d}"

        order_item = {
            "product_id": product["id"],
            "name": product["name"],
            "quantity": quantity,
            "unit_price": unit_price,
            "currency": currency,
            "color": product.get("color"),
            "size": chosen_size,
            "line_total": line_total,
        }

        order = {
            "id": order_id,
            "items": [order_item],
            "total": line_total,
            "currency": currency,
            "created_at": datetime.utcnow().isoformat(),
        }

        orders.append(order)
        save_orders(orders)

        logger.info(f"[Order] Created order {order_id} from text: {req}")

        size_txt = f", size {chosen_size}" if chosen_size else ""
        return (
            f"Your order {order_id} is created: {quantity} x {product['name']}"
            f"{size_txt} for a total of {currency} {line_total}."
        )

    @function_tool()
    async def get_last_order_summary(
        self,
        context: RunContext,
    ) -> str:
        """
        Return a short summary of the most recent order.
        """
        orders = load_orders()
        if not orders:
            return "You haven't placed any orders yet in this demo."

        last = orders[-1]
        items = last.get("items", [])
        if not items:
            return "Your last order appears to be empty."

        lines = []
        for item in items:
            name = item.get("name", "Unknown item")
            qty = item.get("quantity", 1)
            color = item.get("color")
            size = item.get("size")
            extra = []
            if color:
                extra.append(color)
            if size:
                extra.append(f"size {size}")
            extra_txt = f" ({', '.join(extra)})" if extra else ""
            lines.append(f"{qty} x {name}{extra_txt}")

        line_str = "; ".join(lines)
        total = last.get("total", 0)
        currency = last.get("currency", "INR")
        order_id = last.get("id", "unknown ID")

        return (
            f"Your most recent order is {order_id}: {line_str}, "
            f"for a total of {currency} {total}."
        )


# ----------------------- Session Setup -----------------------


def prewarm(proc: JobProcess):
    proc.userdata["vad"] = silero.VAD.load()


async def entrypoint(ctx: JobContext):
    ctx.log_context_fields = {"room": ctx.room.name}

    logger.info(f"Day 9 FalconStore – catalog has {len(CATALOG)} products.")

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
        agent=FalconStoreAgent(),
        room=ctx.room,
        room_input_options=RoomInputOptions(
            noise_cancellation=noise_cancellation.BVC(),
        ),
    )

    await ctx.connect()


if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint, prewarm_fnc=prewarm))
