# Day 3: Health & Wellness Voice Companion

## Objective
Build a daily health & wellness voice companion that conducts supportive check-ins and persists conversation data.

## Core Features
- [x] Daily mood and energy check-ins
- [x] Goal setting and intention tracking
- [x] JSON persistence (wellness_log.json)
- [x] Reference to previous sessions
- [x] Grounded, non-medical advice

## Implementation
- Voice-based daily wellness check-ins
- JSON file storage for session history
- Supportive conversation without medical claims
- Simple goal tracking and reflection

## Advanced Features (Optional)
- [ ] MCP integration for task management
- [ ] Weekly reflection analytics
- [ ] Follow-up reminders via MCP tools

## Testing
1. Start the agent: `uv run python src/agent.py dev`
2. Open frontend: `pnpm dev`
3. Have a wellness check-in conversation
4. Verify `wellness_log.json` is created/updated

## Demo
[Add demo video link here for LinkedIn post]

## LinkedIn Post Requirements
- Record video showing conversation + JSON persistence
- Tag: @Murf AI
- Hashtags: #MurfAIVoiceAgentsChallenge #10DaysofAIVoiceAgents
- Mention: Building with fastest TTS API - Murf Falcon