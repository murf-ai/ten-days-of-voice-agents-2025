# Razorpay SDR Voice Agent (LiveKit Agent)
# This file contains:
# 1) SAMPLE_FAQ JSON data for Razorpay (fallback if external file missing)
# 2) A LiveKit Agent subclass that behaves as an SDR for Razorpay
# 3) Lead collection and saving (JSON files saved to ./leads)
# 4) Simple FAQ keyword search and answer behavior

import json
import logging
from datetime import datetime
from pathlib import Path
import os

from dotenv import load_dotenv

from livekit.agents import (
    Agent,
    AgentSession,
    JobContext,
    JobProcess,
    RoomInputOptions,
    WorkerOptions,
    cli,
    tokenize,
)
from livekit.plugins import murf, deepgram, noise_cancellation, silero
from livekit.plugins.turn_detector.multilingual import MultilingualModel

logger = logging.getLogger("razorpay_sdr")
load_dotenv(".env.local")

# -----------------------------------------
# Sample FAQ content (fallback) — also save this to shared-data/razorpay_faq.json
# You can expand this JSON with more entries or replace it with your own.
# -----------------------------------------
SAMPLE_FAQ = [
    {
        "id": "what_is_razorpay",
        "question": "What is Razorpay?",
        "answer": "Razorpay is a full-stack financial solutions company that enables businesses in India to accept, process and disburse payments across multiple modes including cards, UPI, netbanking and wallets.",
        "keywords": ["what is razorpay", "razorpay", "what do you do", "payments"]
    },
    {
        "id": "pricing_basic",
        "question": "How much does Razorpay charge?",
        "answer": "Razorpay publishes simple and transparent pricing. Platform fees typically start around 2% per transaction (GST extra). Enterprise/custom pricing is available for high volume merchants.",
        "keywords": ["price", "pricing", "charges", "fee", "cost"]
    },
    {
        "id": "products_overview",
        "question": "Which products does Razorpay offer?",
        "answer": "Razorpay's product suite includes Payment Gateway, Payment Links, Payment Pages, Subscriptions, Invoices, RazorpayX payouts and corporate cards, and lending/Capital offerings.",
        "keywords": ["products", "offer", "payment gateway", "subscriptions", "invoices", "razorpayx"]
    },
    {
        "id": "sandbox",
        "question": "Can I test integrations?",
        "answer": "Yes — Razorpay provides a sandbox environment with test API keys so you can test integrations before going live.",
        "keywords": ["sandbox", "test", "test mode", "integration"]
    },
    {
        "id": "free_tier",
        "question": "Do you have a free tier?",
        "answer": "Razorpay does not charge setup or maintenance fees for many of its core products; pricing is typically transaction-based. For exact details, consult the pricing page or contact sales for Enterprise plans.",
        "keywords": ["free", "free tier", "trial", "no setup fee"]
    }
]

# Optionally write the sample FAQ to shared-data so the agent can load it from disk
FAQ_PATH = Path("shared-data/razorpay_faq.json")
FAQ_PATH.parent.mkdir(parents=True, exist_ok=True)
if not FAQ_PATH.exists():
    with open(FAQ_PATH, "w", encoding="utf-8") as f:
        json.dump(SAMPLE_FAQ, f, indent=2)

# -----------------------------------------
# Load FAQ helper
# -----------------------------------------

def load_faq():
    try:
        with open(FAQ_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return SAMPLE_FAQ

faq_content = load_faq()

# -----------------------------------------
# SDR State and lead fields
# -----------------------------------------
lead_fields = [
    {"key": "name", "prompt": "Can I get your full name?"},
    {"key": "company", "prompt": "Which company are you from?"},
    {"key": "email", "prompt": "What's the best email to reach you on?"},
    {"key": "role", "prompt": "What's your role there?"},
    {"key": "use_case", "prompt": "How do you plan to use Razorpay?"},
    {"key": "team_size", "prompt": "What's your team size or expected volume?"},
    {"key": "timeline", "prompt": "What's your timeline to go live — now, soon, or later?"}
]

# -----------------------------------------
# Utility: simple keyword search over FAQ
# -----------------------------------------

def find_faq_answer(question_text):
    q = question_text.lower()
    # first try keyword match
    for entry in faq_content:
        for kw in entry.get("keywords", []):
            if kw in q:
                return entry["answer"], entry
    # fallback: substring match on question/answer
    for entry in faq_content:
        if entry.get("question") and entry["question"].lower() in q:
            return entry["answer"], entry
    # no match
    return None, None

# -----------------------------------------
# Agent Class: RazorpaySDR
# -----------------------------------------
class RazorpaySDR(Agent):
    def __init__(self):
        super().__init__(
            instructions=(
                "You are Razorpay's voice SDR. Greet warmly, ask what brought the visitor here, discover their needs, "
                "answer product/pricing questions using the loaded FAQ (do not invent facts), and collect lead info. "
                "Collect: name, company, email, role, use_case, team_size, timeline. "
                "When the user says they're done, give a short summary and save the lead to a JSON file."
            )
        )
        # per-session state
        self.sessions = {}

    async def on_join(self, context):
        # initialize session state
        sid = context.session.session_id if hasattr(context, 'session') else str(datetime.utcnow().timestamp())
        self.sessions[sid] = {
            "lead": {},
            "collecting": False,
            "next_field": 0,
            "qualified": False,
        }
        await context.send_speech(
            "Hello! Welcome to Razorpay. I'm your sales assistant. What brought you here today and what are you working on?"
        )

    async def on_user_message(self, message, context):
        sid = context.session.session_id if hasattr(context, 'session') else str(datetime.utcnow().timestamp())
        state = self.sessions.get(sid, {"lead": {}, "collecting": False, "next_field": 0, "qualified": False})
        msg = (message.text or "").strip()
        lmsg = msg.lower()

        # End-of-call detection
        if any(phrase in lmsg for phrase in ["that's all", "i'm done", "thanks", "thank you", "bye", "goodbye"]):
            # finish: provide summary and save
            await self.finish_call(context, state)
            return

        # If user asks a product/pricing question, answer from FAQ
        if any(w in lmsg for w in ["price", "pricing", "cost", "charge", "what do you do", "what is razorpay", "products", "subscription", "free tier", "sandbox"]):
            ans, entry = find_faq_answer(msg)
            if ans:
                await context.send_speech(ans)
            else:
                await context.send_speech("I don't have the exact info in my FAQ right now — would you like me to connect you to sales or share our pricing page link?")
            # after answering, optionally start lead capture if not started
            if not state["collecting"]:
                # gently ask qualification
                await context.send_speech("If you'd like, I can save your details so our sales team can follow up. May I get some quick info?")
                state["collecting"] = True
                state["next_field"] = 0
                self.sessions[sid] = state
                await context.send_speech(lead_fields[0]["prompt"])
            return

        # If currently collecting lead info, record answer for current field
        if state["collecting"] and state["next_field"] < len(lead_fields):
            key = lead_fields[state["next_field"]]["key"]
            # naive mapping: accept the message as the field value
            state["lead"][key] = msg
            state["next_field"] += 1
            if state["next_field"] < len(lead_fields):
                await context.send_speech(lead_fields[state["next_field"]]["prompt"])
            else:
                # finished collecting
                await context.send_speech("Thanks — I have all the details. Would you like a quick summary?")
            self.sessions[sid] = state
            return

        # If user expresses interest (e.g., 'interested', 'sign up', 'get started'), begin collection
        if any(w in lmsg for w in ["interested", "sign up", "get started", "contact", "sales"]):
            if not state["collecting"]:
                state["collecting"] = True
                state["next_field"] = 0
                self.sessions[sid] = state
                await context.send_speech("Great — I'll quickly capture a few details so our sales team can reach out.")
                await context.send_speech(lead_fields[0]["prompt"])
            else:
                await context.send_speech("We're already capturing your details. " + (lead_fields[state["next_field"]]["prompt"]))
            return

        # If nothing else: ask a clarifying question to keep conversation focused
        await context.send_speech("Thanks for that. Could you tell me more — what product are you looking at, or do you have a specific question about payments?")

    async def finish_call(self, context, state):
        lead = state.get("lead", {})
        # Build summary
        name = lead.get("name", "(not provided)")
        company = lead.get("company", "(not provided)")
        role = lead.get("role", "(not provided)")
        use_case = lead.get("use_case", "(not provided)")
        timeline = lead.get("timeline", "(not provided)")

        summary = f"Summary: {name} from {company}, role {role}. Use case: {use_case}. Timeline: {timeline}."
        await context.send_speech("Thanks for the chat. " + summary + " We'll have someone from our team follow up.")

        # Save lead JSON
        outdir = Path("leads")
        outdir.mkdir(parents=True, exist_ok=True)
        ts = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
        fname = outdir / f"lead_{ts}.json"
        with open(fname, "w", encoding="utf-8") as f:
            json.dump(lead, f, indent=2)
        logger.info(f"Saved lead to {fname}")

# -----------------------------------------
# VAD prewarm
# -----------------------------------------
vad_model = silero.VAD.load()

def prewarm(proc: JobProcess):
    proc.userdata["vad"] = vad_model

# -----------------------------------------
# Entrypoint (same pattern as provided example)
# -----------------------------------------
async def entrypoint(ctx: JobContext):
    session = AgentSession(
        stt=deepgram.STT(model="nova-3"),
        llm=None,  # rely on Agent instructions + local logic; if you want to add LLM, set it here
        tts=murf.TTS(voice="en-IN-arpan", style="Conversational"),
        turn_detection=MultilingualModel(),
        vad=ctx.proc.userdata["vad"],
        preemptive_generation=True,
    )

    await session.start(
        agent=RazorpaySDR(),
        room=ctx.room,
        room_input_options=RoomInputOptions(noise_cancellation=noise_cancellation.BVC()),
    )

    await ctx.connect()

if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint, prewarm_fnc=prewarm))
