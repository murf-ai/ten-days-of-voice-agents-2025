# Day 3 – Health & Wellness Voice Companion

Today you will build a health and wellness–oriented voice agent that acts as a supportive, but realistic and grounded companion.

## The core idea:

Each day, the agent checks in with the user about their mood and goals, has a short conversation, and stores the results in a JSON file so it can refer back to previous days.

## Primary Goal (Required)

Build a daily health & wellness voice companion that:

- Uses a clear, grounded system prompt.
- Conducts short daily check-ins via voice.
- Persists the key data from each check-in in a JSON file.
- Uses past data (from JSON) to inform the next conversation in a basic way.

## Behaviour Requirements

Your agent should:

### Ask about mood and energy

**Example topics (but not hard-coded):**
- "How are you feeling today?"
- "What's your energy like?"
- "Anything stressing you out right now?"

**Avoid diagnosis or medical claims. This is a supportive check-in companion, not a clinician.**

### Ask about intentions / objectives for the day

**Simple, practical goals:**
- "What are 1–3 things you'd like to get done today?"
- "Is there anything you want to do for yourself (rest, exercise, hobbies)?"

### Offer simple, realistic advice or reflections

**Suggestions should be:**
- Small, actionable, and grounded.
- Non-medical, non-diagnostic.

**Examples of advice style:**
- Break large goals into smaller steps.
- Encourage short breaks.
- Offer simple grounding ideas (e.g., "take a 5-minute walk").

### Close the check-in with a brief recap

**Repeat back:**
- Today's mood summary.
- The main 1–3 objectives.
- Confirm: "Does this sound right?"

## Use JSON-based persistence

- After each check-in, write an entry to a JSON file from the Python backend.
- On a new session:
  - Read the JSON file.
  - Provide at least one small reference to previous check-ins.

**For example:** "Last time we talked, you mentioned being low on energy. How does today compare?"

## Data Persistence Requirements

Store data in a single JSON file (e.g., `wellness_log.json`).

Each session entry should at least contain:

- Date/time of the check-in
- Self-reported mood (text, or a simple scale)
- One or more stated objectives / intentions
- Optional: a short agent-generated summary sentence

You can choose the exact schema, but keep it consistent and human-readable.

## Resources:

- https://docs.livekit.io/agents/build/tools/
- https://docs.livekit.io/agents/build/agents-handoffs/#passing-state
- https://docs.livekit.io/agents/build/tasks/
- https://github.com/livekit/agents/blob/main/examples/drive-thru/agent.py

If you achieve everything in this section, you have completed the Day 3 primary goal.

