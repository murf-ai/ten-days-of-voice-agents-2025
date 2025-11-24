# Changes from Day 2 to Day 3

## Overview
Transformed the coffee shop barista agent into a health & wellness companion.

## Major Changes

### 1. Agent Class Rename
- **Before:** `BaristaAgent`
- **After:** `WellnessAgent`

### 2. Agent Persona
- **Before:** Alex, friendly barista at Brew & Bean Coffee Shop
- **After:** Alex from Cult.fit, health & wellness companion

### 3. System Prompt
**Before:**
- Coffee order taking
- Collect: drinkType, size, milk, extras, name
- Fast, brief responses (5-10 words)

**After:**
- Daily wellness check-ins
- Collect: mood, energy, stress, objectives
- Conversational, supportive responses
- Explicitly avoids medical diagnosis
- References previous check-ins

### 4. State Management

**Before - ORDER_STATE:**
```python
{
    "drinkType": None,
    "size": None,
    "milk": None,
    "extras": [],
    "name": None,
}
```

**After - SESSION_STATE:**
```python
{
    "mood": None,
    "energy": None,
    "stress_factors": None,
    "objectives": [],
    "session_started": False,
}
```

### 5. Function Tools

**Before (Coffee Order Tools):**
- `update_drink_type(drink_type: str)`
- `update_size(size: str)`
- `update_milk(milk: str)`
- `update_extras(extras: list[str])`
- `update_name(name: str)`
- `check_order_complete()`
- `save_order()`

**After (Wellness Tools):**
- `record_mood(mood: str)`
- `record_energy(energy_level: str)`
- `record_stress(stress_description: str)`
- `record_objectives(objectives: list[str])`
- `save_checkin(summary: str)`
- `get_previous_checkin_context()`

### 6. Data Persistence

**Before:**
- Multiple JSON files in `orders/` directory
- Filename: `order_{name}_{timestamp}.json`
- One file per order
- No historical context

**After:**
- Single JSON file: `wellness_log.json`
- Array of all check-ins
- Historical context loaded on agent initialization
- Previous check-ins referenced in conversation

### 7. Data Schema

**Before (Coffee Order):**
```json
{
  "drinkType": "latte",
  "size": "medium",
  "milk": "oat milk",
  "extras": ["extra shot"],
  "name": "Robin",
  "timestamp": "2025-11-23T14:15:35"
}
```

**After (Wellness Check-in):**
```json
{
  "date": "2025-11-24",
  "timestamp": "2025-11-24T10:30:00.123456",
  "mood": "good and energetic",
  "energy": "high",
  "stress_factors": "work deadline",
  "objectives": ["Complete report", "Go for walk"],
  "summary": "User feeling energetic..."
}
```

### 8. Helper Functions

**Added:**
- `load_wellness_history()` - Load all check-ins from JSON
- `get_last_checkin()` - Get most recent check-in
- Dynamic system prompt with previous check-in context

**Removed:**
- Order directory creation logic
- Name sanitization for filenames
- Order state reset logic

### 9. Frontend Data Publishing

**Before:**
```python
{
    "type": "order_update",
    "data": { drinkType, size, milk, extras, name }
}
```

**After:**
```python
{
    "type": "wellness_update",
    "data": { mood, energy, stress_factors, objectives }
}
```

### 10. Tests Updated

**Before:**
- `test_offers_assistance()` - Generic greeting
- `test_grounding()` - Refusing unknown info
- `test_refuses_harmful_request()` - Refusing hacking

**After:**
- `test_greets_from_cultfit()` - Cult.fit introduction
- `test_refuses_medical_advice()` - No medical diagnosis
- `test_wellness_checkin_flow()` - Wellness conversation

## Files Modified

1. **backend/src/agent.py** - Complete rewrite
2. **backend/tests/test_agent.py** - All tests updated
3. **backend/wellness_log.json** - New file (created on first use)

## Files Created

1. **Day 3/README.md** - Full documentation
2. **Day 3/QUICKSTART.md** - Quick start guide
3. **Day 3/CHANGES.md** - This file
4. **backend/wellness_log_example.json** - Example data

## Key Behavioral Differences

### Conversation Style
- **Before:** Fast, transactional (5-10 words)
- **After:** Conversational, supportive, empathetic

### Goal
- **Before:** Complete coffee order quickly
- **After:** Meaningful wellness check-in

### Memory
- **Before:** No memory between sessions
- **After:** References previous check-ins

### Advice
- **Before:** None (just order taking)
- **After:** Simple, practical wellness suggestions

### Boundaries
- **Before:** Stay on topic (coffee only)
- **After:** No medical diagnosis, supportive only

## Preserved Elements

✅ LiveKit agent framework
✅ Murf Falcon TTS
✅ Google Gemini LLM
✅ Deepgram STT
✅ Function tools pattern
✅ Data publishing to frontend
✅ JSON persistence
✅ Logging infrastructure
✅ Test structure

