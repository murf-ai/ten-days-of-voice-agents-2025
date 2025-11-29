# Day 1: Get Your Starter Voice Agent Running

## Objective
Set up and run the starter voice agent end-to-end (backend + frontend)

## Tasks Completed
- [x] Fork/clone the starter repository
- [x] Backend setup with dependencies
- [x] Frontend setup with pnpm
- [x] LiveKit server configuration
- [x] Environment variables configured
- [x] Successful voice conversation test

## Setup Steps
1. Install dependencies: `uv sync` (backend), `pnpm install` (frontend)
2. Configure `.env.local` files with API keys
3. Start LiveKit server: `livekit-server --dev`
4. Run backend: `uv run python src/agent.py dev`
5. Run frontend: `pnpm dev`
6. Test conversation at http://localhost:3000

## Demo Requirements
- Record video of voice conversation with agent
- Post on LinkedIn with:
  - Tag: @Murf AI
  - Hashtags: #MurfAIVoiceAgentsChallenge #10DaysofAIVoiceAgents
  - Mention: Murf Falcon TTS API