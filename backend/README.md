🎙️ AI Voice Agent – Day 1 (Murf Falcon TTS + LiveKit Agents)

This project is my Day 1 submission for the AI Voice Agents Challenge by Murf.ai.

It uses Murf Falcon — the fastest TTS API ⚡ to generate ultra-fast natural speech for real-time conversations, powered by LiveKit Agents.

✅ What This Backend Does

✅ Real-time voice conversation

✅ Murf Falcon TTS for fast responses

✅ Speech-to-text + LLM pipeline

✅ Turn detection & noise handling

✅ Ready for web, mobile, or phone calling

✅ A solid base for customer support bots, assistants, call agents, etc.

🧩 Tech Stack
Component	Service
Voice Streaming	LiveKit Cloud
Text-to-Speech	Murf Falcon TTS
Speech-to-Text	LiveKit Models
LLM	OpenAI / Custom
Backend	Python + LiveKit Agents
Deployment	Docker-ready
🚀 Setup & Run
1️⃣ Install Dependencies
uv sync

2️⃣ Create Environment File
cp .env.example .env.local


Fill in:

LIVEKIT_URL

LIVEKIT_API_KEY

LIVEKIT_API_SECRET

(From https://cloud.livekit.io
)

3️⃣ Download Required Models
uv run python src/agent.py download-files

4️⃣ Run in Console
uv run python src/agent.py console

5️⃣ Run Dev Server (Frontend/Telephony)
uv run python src/agent.py dev

✅ Production
uv run python src/agent.py start

🌐 Frontend Compatibility

This backend can connect to:

✅ Web (React/Next.js)

✅ iOS / Android / Flutter / React Native

✅ SIP / Phone calling

📦 Deployment

A ready-to-use Dockerfile is included.
You can deploy to:

LiveKit Cloud

Your own server

Any container platform

🔥 Why Murf Falcon?

⚡ Fastest TTS response time

🔊 High-quality natural speech

🚀 Built for real-time agents

Perfect for practical, real-world voice applications.

📜 License

MIT License. See LICENSE.

✅ Challenge Note

This project was built as part of AI Voice Agents Challenge – Day 1, showcasing a real working backend powered by Murf Falcon TTS.
