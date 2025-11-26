# ===========================================
# Razorpay SDR Voice Agent (LiveKit)
# ===========================================

import json
import logging
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

from livekit.agents import (
    Agent,
    AgentSession,
    JobContext,
    JobProcess,
    RoomInputOptions,
    WorkerOptions,
    cli,
)

from livekit.plugins import (
    deepgram,
    google,
    murf,
    noise_cancellation,
    silero,
)
from livekit.plugins.turn_detector.multilingual import MultilingualModel


# ------------------------------------------
# Logging + ENV
# ------------------------------------------
logger = logging.getLogger("razorpay_sdr")
load_dotenv(".env.local")


# ------------------------------------------
# Load FAQ
# ------------------------------------------
SAMPLE_FAQ = [
    {
        "id": "what_is_razorpay",
        "question": "What is Razorpay?",
        "answer": "Razorpay is a full-stack financial platform that helps businesses accept and manage payments across UPI, cards, netbanking and more.",
        "keywords": ["what is razorpay", "razorpay", "payments", "gateway"],
    },
    {
        "id": "pricing",
        "question": "How much does Razorpay charge?",
        "answer": "Razorpay pricing typically starts at around 2% per successful transaction. Enterprise pricing is also available.",
        "keywords": ["price", "pricing", "cost", "charges"],
    },
]

FAQ_PATH = Path("shared-data/razorpay_faq.json")
FAQ_PATH.parent.mkdir(exist_ok=True, parents=True)

if not FAQ_PATH.exists():
    with open(FAQ_PATH, "w") as f:
        json.dump(SAMPLE_FAQ, f, indent=2)


def load_faq():
    try:
        return json.load(open(FAQ_PATH))
    except:
        return SAMPLE_FAQ


faq_content = load_faq()


def find_faq(q):
    q = q.lower()
    for entry in faq_content:
        for kw in entry.get("keywords", []):
            if kw in q:
                return entry["answer"]
    return None


# ------------------------------------------
# SDR Agent Class
# ------------------------------------------
class RazorpaySDR(Agent):
    def __init__(self):
        super().__init__(
            instructions=(
                "You are Razorpay's SDR. Greet warmly, answer FAQs using provided JSON, "
                "and collect lead details: name, company, email, role, use_case, team_size, timeline."
            )
        )
        self.sessions = {}

    async def on_join(self, ctx):
        sid = ctx.session.session_id
        self.sessions[sid] = {
            "lead": {},
            "collecting": False,
            "field_index": 0,
        }

        await ctx.send_speech(
            "Hello! Welcome to Razorpay. How can I assist you today?"
        )

    async def on_user_message(self, message, ctx):
        sid = ctx.session.session_id
        state = self.sessions[sid]
        msg = (message.text or "").strip().lower()

        # -------------- End the call --------------
        if any(x in msg for x in ["bye", "thanks", "thank you", "that’s all"]):
            await self.finish(ctx, state)
            return

        # -------------- FAQ detection --------------
        faq = find_faq(msg)
        if faq:
            await ctx.send_speech(faq)
            await ctx.send_speech(
                "Would you like me to collect your details so our sales team can reach out?"
            )
            state["collecting"] = True
            await ctx.send_speech("May I have your full name?")
            return

        # -------------- Lead Collection --------------
        fields = [
            "name",
            "company",
            "email",
            "role",
            "use_case",
            "team_size",
            "timeline",
        ]

        prompts = [
            "Which company are you from?",
            "What is the best email to reach you on?",
            "What's your role there?",
            "How do you plan to use Razorpay?",
            "What's your expected team size or volume?",
            "When do you plan to go live?",
        ]

        if state["collecting"]:
            idx = state["field_index"]
            state["lead"][fields[idx]] = msg
            state["field_index"] += 1

            if idx < len(prompts):
                await ctx.send_speech(prompts[idx])
            else:
                await ctx.send_speech("Great! I have all the information.")
                await self.finish(ctx, state)
            return

        # -------------- Default response --------------
        await ctx.send_speech(
            "Sure! Are you exploring Razorpay's payments, payouts, or subscriptions?"
        )

    async def finish(self, ctx, state):
        lead = state["lead"]
        ts = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")

        outdir = Path("leads")
        outdir.mkdir(exist_ok=True)

        with open(outdir / f"lead_{ts}.json", "w") as f:
            json.dump(lead, f, indent=2)

        await ctx.send_speech(
            "Thank you! Your details have been saved. Our team will reach out shortly."
        )


# ------------------------------------------
# Prewarm VAD
# ------------------------------------------
vad_model = silero.VAD.load()


def prewarm(proc: JobProcess):
    proc.userdata["vad"] = vad_model


# ------------------------------------------
# Entrypoint — EXACT same structure you asked for
# ------------------------------------------
async def entrypoint(ctx: JobContext):
    session = AgentSession(
        stt=deepgram.STT(model="nova-3"),
        llm=google.LLM(model="gemini-2.5-flash"),
         tts=murf.TTS(voice="en-US-matthew", style="Conversation"),
        turn_detection=MultilingualModel(),
        vad=ctx.proc.userdata["vad"],
        preemptive_generation=True,
    )

    await session.start(
        agent=RazorpaySDR(),
        room=ctx.room,
        room_input_options=RoomInputOptions(
            noise_cancellation=noise_cancellation.BVC()
        ),
    )

    await ctx.connect()


if __name__ == "__main__":
    cli.run_app(
        WorkerOptions(
            entrypoint_fnc=entrypoint,
            prewarm_fnc=prewarm,
        )
    )
