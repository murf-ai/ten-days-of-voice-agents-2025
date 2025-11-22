🎙️ AI Voice Agent – Day 1 (Murf Falcon TTS + LiveKit Agents)

This project is my Day 1 submission for the AI Voice Agents Challenge by Murf.ai.

It uses Murf Falcon — the fastest TTS API ⚡ to deliver ultra-fast, natural voice responses in a real-time voice agent.

✅ What This Project Does

This backend provides:

✅ A working voice AI assistant

✅ Real-time conversation using LiveKit Agents

✅ Murf Falcon TTS for lightning-fast voice synthesis

✅ Speech-to-text + LLM pipeline

✅ Turn detection & background noise handling

✅ Ready for web, mobile, or telephony frontends

Perfect base to extend into customer support bots, voice companions, call agents, and more ✅

🧩 Tech Stack
Component	Service
Voice Transport	LiveKit Cloud
Text-to-Speech	Murf Falcon TTS
Speech-to-Text	LiveKit Pipeline Models
LLM	OpenAI / Custom models
Backend	Python + LiveKit Agents
Deployment	Docker-ready
🚀 Getting Started (Local Setup)
1️⃣ Clone & Install
uv sync

2️⃣ Environment Setup

Copy the example file:

cp .env.example .env.local


Fill in:

LIVEKIT_URL

LIVEKIT_API_KEY

LIVEKIT_API_SECRET

(From https://cloud.livekit.io/
)

3️⃣ Download Required Models
uv run python src/agent.py download-files

4️⃣ Run Voice Agent in Terminal
uv run python src/agent.py console

5️⃣ Run Dev Server (For frontend/telephony)
uv run python src/agent.py dev

✅ Production Command
uv run python src/agent.py start

🌐 Frontend Options

You can connect this backend to:

✅ Web (React/Next.js)

✅ iOS / Android / Flutter / React Native

✅ SIP / Phone calling

Starter templates are available in LiveKit examples.

🧪 Testing
uv run pytest

📦 Deployment

A production-ready Dockerfile is included.
You can deploy to:

LiveKit Cloud

Your own server

Any container platform

🔥 Why Murf Falcon?

⚡ Fastest TTS response time

🔊 High-quality natural voices

🚀 Built for real-time voice agents

This challenge focuses on building practical, real-world voice systems — and Falcon makes that possible.

📜 License

MIT License. See LICENSE for details.

✅ Challenge Note

This project was completed as part of AI Voice Agents Challenge – Day 1, and showcases a working backend voice agent powered by Murf Falcon TTS.
