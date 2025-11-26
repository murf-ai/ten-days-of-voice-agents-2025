import logging
import json
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any

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

# ---------- Helper: load Zomato FAQ content ----------


def load_zomato_faq() -> Dict[str, Any]:
    """
    Load Zomato FAQ content from shared-data/day5_zomato_faq.json.
    """
    try:
        base_dir = Path(__file__).resolve().parent.parent  # backend/
        path = base_dir / "shared-data" / "day5_zomato_faq.json"
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, dict) and "faqs" in data:
                return data
    except Exception as e:
        logger.warning(f"Failed to load day5_zomato_faq.json: {e}")

    # Very small fallback if file missing
    return {
        "company": "Zomato",
        "description": "Zomato is an Indian food delivery and restaurant discovery platform.",
        "faqs": [
            {
                "id": "fallback",
                "q": "What does Zomato do?",
                "a": "Zomato helps customers discover restaurants and order food online, and helps restaurants get more orders.",
                "tags": ["zomato", "product"]
            }
        ],
    }


class ZomatoSDR(Agent):
    def __init__(self, faq_data: Dict[str, Any]) -> None:
        self.faq_data = faq_data
        self.faq_list: List[Dict[str, Any]] = faq_data.get("faqs", [])
        self.company_name: str = faq_data.get("company", "Zomato")
        self.company_desc: str = faq_data.get("description", "")

        # Lead state kept in memory during the call
        self.current_lead: Dict[str, Any] = {
            "name": None,
            "company": None,
            "email": None,
            "role": None,
            "use_case": None,
            "team_size": None,
            "timeline": None,
        }

        # Where to store leads
        base_dir = Path(__file__).resolve().parent.parent  # backend/
        leads_dir = base_dir / "leads"
        leads_dir.mkdir(parents=True, exist_ok=True)
        self.leads_path = leads_dir / "day5_leads.json"

        instructions = f"""
You are a warm, professional Sales Development Representative (SDR) for {self.company_name}.

Company overview:
{self.company_desc}

Your goals:
1. Greet visitors warmly and explain that you are an SDR for {self.company_name}.
2. Ask what brought them here and what they are working on.
3. Keep the conversation focused on understanding their business and whether {self.company_name} is a good fit.
4. Answer questions about the company, product, and pricing ONLY using the FAQ content and the `answer_faq` tool.
5. Collect key lead details naturally during the conversation:
   - Name
   - Company
   - Email
   - Role
   - Use case (what they want to use {self.company_name} for)
   - Team size
   - Timeline (now / soon / later)
   When the user gives any of these, call the `save_lead_field` tool to store them.

FAQ usage:
- When the user asks things like:
  - "What does your product do?"
  - "Who is this for?"
  - "Do you have a free tier?"
  - "How does pricing work for restaurants?"
  Use the `answer_faq` tool with their question.
- Do NOT make up product or pricing details beyond what the FAQ provides.
- If the FAQ does not contain the answer, say you are not sure and that a human teammate can share more details later.

End-of-call behavior:
- When the user says phrases like:
  "That's all", "I'm done", "Thanks, that's it", or clearly ends the conversation:
  1. Make sure you have collected as many lead fields as possible.
  2. Call the `finalize_lead` tool ONCE to store the lead in JSON.
  3. Then give a short verbal summary including:
     - Their name and company (if known)
     - Use case
     - Team size
     - Timeline
  4. End politely and thank them for their time.

Important rules:
- You are not a support agent; you are an SDR focusing on qualification and basic FAQs.
- Be concise, friendly, and professional.
- Never talk about tools, JSON, files, or internal implementation.
- Do not show raw function calls or code like `tool_code` in your replies.
"""
        super().__init__(instructions=instructions)

    # ---------- Internal: simple FAQ search ----------

    def _best_faq_match(self, question: str) -> Dict[str, Any] | None:
        q_lower = question.lower()
        best_score = 0
        best_entry = None

        for entry in self.faq_list:
            text = (
                (entry.get("q") or "") + " "
                + (entry.get("a") or "") + " "
                + " ".join(entry.get("tags") or [])
            ).lower()
            score = 0
            # simple keyword overlap
            for token in q_lower.split():
                if token in text:
                    score += 1
            if score > best_score:
                best_score = score
                best_entry = entry

        # if nothing matched, just return first entry
        if best_entry is None and self.faq_list:
            return self.faq_list[0]
        return best_entry

    # ---------- Tools ----------

    @function_tool()
    async def answer_faq(
        self,
        context: RunContext,
        question: str,
    ) -> str:
        """
        Look up an answer in the Zomato FAQ based on the user's question.
        Only use this to answer product / company / pricing / who-is-it-for type questions.
        """
        entry = self._best_faq_match(question)
        if not entry:
            return (
                "I'm not completely sure about that specific detail. A teammate from Zomato can share more information with you later."
            )
        return entry.get("a", "")

    @function_tool()
    async def save_lead_field(
        self,
        context: RunContext,
        field: str,
        value: str,
    ) -> str:
        """
        Save a single lead field during the conversation.

        Args:
            field: one of: name, company, email, role, use_case, team_size, timeline
            value: the value user provided
        """
        field = field.strip().lower()
        if field not in self.current_lead:
            return "I can't store that field, but thank you for sharing."

        self.current_lead[field] = value.strip()
        logger.info(f"[Lead] Updated field {field} = {value}")
        return f"Got it, I've noted your {field} as {value}."

    @function_tool()
    async def finalize_lead(self, context: RunContext) -> str:
        """
        Write the collected lead information to a JSON file and return a short summary.
        """
        lead = self.current_lead.copy()
        lead["timestamp"] = datetime.utcnow().isoformat()

        # Load existing leads
        try:
            if self.leads_path.exists():
                with self.leads_path.open("r", encoding="utf-8") as f:
                    data = json.load(f)
            else:
                data = []
        except Exception as e:
            logger.warning(f"Failed to read leads file, starting new list. Error: {e}")
            data = []

        if not isinstance(data, list):
            data = []

        data.append(lead)

        # Write back
        with self.leads_path.open("w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        logger.info(f"[Lead] Saved lead: {lead}")

        name = lead.get("name") or "Unknown name"
        company = lead.get("company") or "Unknown company"
        email = lead.get("email") or "No email provided"
        role = lead.get("role") or "Unknown role"
        use_case = lead.get("use_case") or "Not clearly specified yet"
        team_size = lead.get("team_size") or "Not specified"
        timeline = lead.get("timeline") or "No timeline mentioned"

        summary = (
            f"Here is the summary I captured: "
            f"{name} from {company}, role {role}. "
            f"Use case: {use_case}. Team size: {team_size}. "
            f"Timeline: {timeline}. Contact email: {email}. "
            "I'll share this with the Zomato team so they can follow up."
        )

        return summary


# ----------------------- Session Setup -----------------------


def prewarm(proc: JobProcess):
    proc.userdata["vad"] = silero.VAD.load()


async def entrypoint(ctx: JobContext):
    ctx.log_context_fields = {"room": ctx.room.name}

    faq_data = load_zomato_faq()
    logger.info(
        f"Day 5 SDR – loaded {len(faq_data.get('faqs', []))} FAQ entries for {faq_data.get('company')}."
    )

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
        agent=ZomatoSDR(faq_data=faq_data),
        room=ctx.room,
        room_input_options=RoomInputOptions(
            noise_cancellation=noise_cancellation.BVC(),
        ),
    )

    await ctx.connect()


if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint, prewarm_fnc=prewarm))
