# Day 3 – Health & Wellness Voice Companion

Today you will build a **health and wellness–oriented voice agent** that acts as a supportive, but realistic and grounded companion.

The core idea:  
Each day, the agent checks in with the user about their mood and goals, has a short conversation, and stores the results in a JSON file so it can refer back to previous days.

---

## Primary Goal (Required)

Build a **daily health & wellness voice companion** that:

1. Uses a clear, grounded system prompt.
2. Conducts short daily check-ins via voice.
3. Persists the key data from each check-in in a JSON file.
4. Uses past data (from JSON) to inform the next conversation in a basic way.

### Behaviour Requirements

Your agent should:

1. Ask about mood and energy

   - Example topics (but not hard-coded):
     - “How are you feeling today?”
     - “What’s your energy like?”
     - “Anything stressing you out right now?”
   - Avoid diagnosis or medical claims. This is a supportive check-in companion, not a clinician.

2. Ask about intentions / objectives for the day

   - Simple, practical goals:
     - “What are 1–3 things you’d like to get done today?”
     - “Is there anything you want to do for yourself (rest, exercise, hobbies)?”

3. Offer simple, realistic advice or reflections

   - Suggestions should be:
     - Small, actionable, and grounded.
     - Non-medical, non-diagnostic.
   - Examples of advice style:
     - Break large goals into smaller steps.
     - Encourage short breaks.
     - Offer simple grounding ideas (e.g., “take a 5-minute walk”).

4. Close the check-in with a brief recap

   - Repeat back:
     - Today’s mood summary.
     - The main 1–3 objectives.
   - Confirm: “Does this sound right?”

5. Use JSON-based persistence
   - After each check-in, write an entry to a JSON file from the Python backend.
   - On a new session:
     - Read the JSON file.
     - Provide at least one small reference to previous check-ins.
       - For example: “Last time we talked, you mentioned being low on energy. How does today compare?”

### Data Persistence Requirements

Store data in a single JSON file (e.g., `wellness_log.json`).

Each session entry should at least contain:

- Date/time of the check-in
- Self-reported mood (text, or a simple scale)
- One or more stated objectives / intentions
- Optional: a short agent-generated summary sentence

You can choose the exact schema, but keep it consistent and human-readable.

#### Resources:
- https://docs.livekit.io/agents/build/tools/
- https://docs.livekit.io/agents/build/agents-handoffs/#passing-state
- https://docs.livekit.io/agents/build/tasks/
- https://github.com/livekit/agents/blob/main/examples/drive-thru/agent.py

If you achieve everything in this section, you have completed the Day 3 primary goal.

---

## Advanced Goals (Optional)

The advanced goals are about:

- Integrating MCP servers so the agent can manage tasks/events in real tools.
- Adding slightly richer insights from the stored data.

#### Resources:
- https://docs.livekit.io/agents/build/tools/#external-tools-and-mcp
- https://github.com/livekit-examples/python-agents-examples/tree/main/mcp
- https://modelcontextprotocol.io/docs/getting-started/intro

---

### Advanced Goal 1: MCP Integration for Tasks/Notes

Connect your voice companion to an MCP server so it can create or update items in an external system when the user sets goals.

Examples (you can pick one, choose your own, or even create your own):

- Notion MCP server:

  - Create a “Daily Wellness” database or page.
  - For each check-in, create a new entry with:
    - Date
    - Mood
    - Objectives
  - Optionally, mark objectives as done in follow-up sessions.

#### Resources:
- https://developers.notion.com/docs/mcp

 

- Todoist MCP server:

  - When the user states objectives like “I want to finish the project report,” turn each into a Todoist task via MCP.
  - Allow simple operations like:
    - “Mark yesterday’s goal as done.”
    - “Show me my tasks for today.”

#### Resources:
- https://mcpmarket.com/server/todo-list

 
- Zapier MCP server:
  - Use Zapier to fan out events:
    - For example, trigger a Zap that logs a summary to a Google Sheet, or sends a reminder, or schedules a google calendar event.

Requirements:

- The MCP connection should be triggered from the Python backend when certain intents are detected:
  - Example: user explicitly says “Turn these into tasks” or “Save this to Notion.”
- The agent should confirm what it did:
  - “I created 3 tasks in Todoist based on your goals.”

#### Resources:
- https://zapier.com/mcp

---

### Advanced Goal 2: Weekly Reflection Using JSON History

Use the JSON file not just as a log, but as a source for simple aggregated insights.

Examples:

- Allow the user to say:
  - “How has my mood been this week?”
  - “Did I follow through on my goals most days?”
- Compute basic aggregates:
  - Average mood score over last N days (if you store a numeric scale).
  - Count of days with at least one objective.
- The agent should:
  - Summarize trends in plain language.
  - Keep it non-judgmental and supportive.

No complex analytics required; straightforward loops over JSON entries are enough.

---

### Advanced Goal 3: Follow-up Reminders via MCP Tools

If you are already using an MCP server (Notion, Todoist, Zapier, etc.), extend it with simple follow-up behaviour.

Examples:

- When the user mentions an important self-care activity (“I want to go for a walk at 6 pm”), offer to:
  - Create a reminder or event through your MCP tool.
- The companion should:
  - Rephrase the reminder back to the user for confirmation.
  - Only call the MCP server after explicit confirmation.

This is mostly about wiring MCP calls to specific conversational moments.

-----

- Step 1: You only need the **primary goal** to complete Day 3; the **Advanced Goals** are for going the extra mile.
- Step 2: **Successfully connect to the Health & Wellness Voice Companion** in your browser and have a conversation.
- Step 3: **Record a short video** of your session with the agent and show the JSON file persisting the conversation in `wellness_log.json`.
- Step 4: **Post the video on LinkedIn** with a description of what you did for the task on Day 3. Also, mention that you are building voice agent using the fastest TTS API - Murf Falcon. Mention that you are part of the **“Murf AI Voice Agent Challenge”** and don't forget to tag the official Murf AI handle. Also, use hashtags **#MurfAIVoiceAgentsChallenge** and **#10DaysofAIVoiceAgents**

Once your agent is running and your LinkedIn post is live, you’ve completed Day 3.