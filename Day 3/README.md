# Day 3 – Health & Wellness Voice Companion

## Overview
A supportive health and wellness voice agent that conducts daily check-ins with users, tracks their mood, energy, stress levels, and daily objectives. The agent introduces itself as **Alex from Cult.fit** and maintains conversation history in a JSON file for continuity across sessions.

## Features Implemented

### ✅ Primary Requirements
- **Clear, grounded system prompt** - Agent is configured as a supportive wellness companion
- **Daily voice check-ins** - Conducts structured wellness conversations
- **JSON persistence** - Stores check-in data in `wellness_log.json`
- **Historical context** - References previous check-ins in new conversations

### ✅ Behavior Requirements

#### 1. Mood and Energy Check
- Asks "How are you feeling today?"
- Asks about energy levels
- Inquires about stress factors
- Records responses using dedicated tools

#### 2. Daily Objectives
- Asks for 1-3 things the user wants to accomplish
- Records objectives for the day
- Keeps goals practical and achievable

#### 3. Realistic Advice
- Offers simple, actionable suggestions
- Breaks large goals into smaller steps
- Suggests short breaks or walks
- Provides grounding techniques
- **Never provides medical diagnosis or advice**

#### 4. Check-in Recap
- Summarizes mood and energy
- Lists the main objectives
- Confirms accuracy with the user
- Saves the complete check-in to JSON

#### 5. Cult.fit Branding
- **Always introduces as "Alex from Cult.fit"**
- Maintains professional wellness companion persona
- Grounded and realistic approach

## Data Persistence

### File Structure
All check-ins are stored in `backend/wellness_log.json` with the following schema:

```json
[
  {
    "date": "2025-11-24",
    "timestamp": "2025-11-24T10:30:00.123456",
    "mood": "good and energetic",
    "energy": "high",
    "stress_factors": "work deadline coming up",
    "objectives": [
      "Complete project report",
      "Go for a 30-minute walk",
      "Call mom"
    ],
    "summary": "User feeling energetic with high energy, focused on work and self-care"
  }
]
```

### Data Fields
- **date**: Date of check-in (YYYY-MM-DD)
- **timestamp**: Full ISO timestamp
- **mood**: User's self-reported mood (text)
- **energy**: Energy level description
- **stress_factors**: What's causing stress or concern
- **objectives**: List of 1-3 daily goals
- **summary**: Agent-generated one-sentence summary

## Agent Tools

The wellness agent has the following function tools:

1. **`record_mood(mood: str)`** - Records user's current mood
2. **`record_energy(energy_level: str)`** - Records energy level
3. **`record_stress(stress_description: str)`** - Records stress factors
4. **`record_objectives(objectives: list[str])`** - Records daily objectives
5. **`save_checkin(summary: str)`** - Saves complete check-in to JSON
6. **`get_previous_checkin_context()`** - Retrieves last check-in for reference

## How to Run

### 1. Start the Backend Agent
```bash
cd backend
uv run python src/agent.py dev
```

### 2. Start the Frontend
```bash
cd frontend
pnpm dev
```

### 3. Access the Application
Open your browser to `http://localhost:3000` and click "Start call"

## Example Conversation Flow

```
Agent: Hi, I'm Alex from Cult.fit. How are you feeling today?

User: I'm feeling pretty good, a bit tired though.

Agent: Got it, you're feeling pretty good. I've noted that. What's your energy like today?

User: Energy is medium, not super high but not low either.

Agent: Energy level noted as medium. Is there anything stressing you out right now?

User: Yeah, I have a work deadline coming up this week.

Agent: I've noted that. Work deadline coming up this week. What are 1-3 things you'd like to get done today?

User: I want to finish the project report, go for a walk, and maybe call my mom.

Agent: Perfect, I've noted your 3 objectives. For that work deadline, try breaking it into smaller tasks - maybe focus on one section of the report at a time. And great that you're planning a walk, that can help with stress. 

Let me recap: You're feeling pretty good with medium energy, dealing with a work deadline. Your main objectives are finishing the project report, going for a walk, and calling your mom. Does this sound right?

User: Yes, that's perfect.

Agent: Perfect! I've saved today's check-in. Take care, and I'll check in with you next time!
```

## Testing

Run the test suite:
```bash
cd backend
uv run pytest
```

Tests include:
- Greeting with Cult.fit introduction
- Refusing medical diagnosis/advice
- Conducting wellness check-in flow

## Technical Implementation

### Agent Class: `WellnessAgent`
- Extends `livekit.agents.Agent`
- Loads previous check-in history on initialization
- Includes context from last check-in in system prompt
- Uses function tools to structure data collection

### State Management
- `SESSION_STATE` tracks current check-in data
- Resets after each successful save
- Publishes updates to frontend via data channel

### Persistence Layer
- `load_wellness_history()` - Loads all check-ins from JSON
- `get_last_checkin()` - Retrieves most recent entry
- `save_checkin()` - Appends new entry to history

## Key Design Decisions

1. **Non-medical approach** - Agent explicitly avoids diagnosis or medical advice
2. **Simple data structure** - Human-readable JSON for easy inspection
3. **Contextual awareness** - References previous check-ins naturally
4. **Grounded advice** - Only practical, actionable suggestions
5. **Cult.fit branding** - Consistent introduction and professional persona

## Files Modified

- `backend/src/agent.py` - Complete rewrite for wellness companion
- `backend/tests/test_agent.py` - Updated tests for wellness agent
- `backend/wellness_log.json` - Created automatically on first check-in

## Next Steps

Potential enhancements:
- Add mood tracking visualization
- Weekly/monthly wellness summaries
- Goal completion tracking
- Integration with fitness tracking APIs
- Reminder system for objectives

