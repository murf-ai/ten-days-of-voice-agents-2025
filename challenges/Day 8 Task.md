# Day 8 – Voice Game Master (D&D-Style Adventure)

Welcome to Day 8!  
Today you’ll turn your voice agent into a **D&D-style Game Master** that runs a story in a specific universe (maybe in the setting of your favorite TV show/ movie) and guides the player through an interactive adventure.

You’ll start with a **simple, single-player story** that only relies on the conversation history, and then (if you want) level up into a **stateful RPG engine** powered by a JSON world model.

---

## Scenario

You are building a **voice-only game master**:

The **system message** for the LLM will define the universe, tone, and rules.  
For example: “You are a Game Master running a fantasy adventure in a world of dragons and magic,” or “You are running a sci-fi survival story on Mars,” etc.

---

## Primary Goal (Required)

> **Build a D&D-style voice Game Master that runs a story in a single universe, using only chat history for context.**

### Minimum Requirements

Your agent should:

1. **Use a clear Game Master (GM) persona**

   - System prompt sets:
     - Universe (fantasy / sci-fi / post-apocalypse / etc.)
     - Tone (dramatic, humorous, spooky)
     - Role: “You are the GM. You describe scenes and ask the player what they do.”

2. **Drive an interactive story using voice**

   - GM describes the current scene.
   - GM ends each message with a **prompt for player action** (“What do you do?”).
   - Player responds by speaking; the agent continues the story based on that.

3. **Maintain continuity with chat history**

   - The GM should remember:
     - Player’s past decisions
     - Named characters / locations

4. **Run a short “session”**

   - A single playthrough should:
     - Last at least a few turns (e.g., 8–15 exchanges).
     - Reach some kind of “mini-arc” (finding something, escaping danger, etc.).

5. **Basic UI**
   - Show the GM’s text messages.
   - Show the player’s transcribed speech.
   - Optional but nice: a “Restart story” button to start a fresh adventure.

If you achieve this, you’ve completed the **Day 8 primary goal**

#### Resources
- https://docs.livekit.io/agents/build/prompting/
- https://docs.livekit.io/agents/build/tools/
---

## Advanced Goals

Pick any **one or more** of these to go beyond a simple GM.  
These will make your agent feel more like a real game engine than just a chat.

---

### 1. JSON World State: Characters, Events, and World Info

> **Goal:** Maintain a structured JSON “world state” that the GM updates and uses to guide the story.

Instead of relying only on past messages, introduce a **Python-side data structure** (in memory is fine) that tracks things like:

- `characters`
  - Player character (name, class, HP, inventory, traits)
  - Important NPCs (name, role, attitude towards player)
- `locations`
  - Current location name, description, known paths
- `events`
  - Key events that have happened (met NPC X, completed quest Y, angered faction Z)
- `quests`
  - Active / completed objectives

The GM should:

1. **Update this JSON state** after each turn (or when something important happens).
2. **Consult this state** when deciding what happens next.
   - Example: If an NPC is dead in the JSON, they shouldn’t suddenly reappear alive.
3. Keep it in a place where you can **inspect it easily** (e.g., log to console or show in UI).

You do _not_ need a database; in-memory JSON per session is enough.

---

### 2. Player Character Sheet & Inventory

> **Goal:** Track player stats and items in the JSON state and expose them to the player.

Build on the world state by adding a **character sheet**:

- HP / health or a simple “status” (Healthy / Injured / Critical)
- Some attributes (e.g., Strength / Intelligence / Luck) – can just be numbers or tags
- Inventory: list of items with optional properties (e.g., “magic sword”, “health potion”)

The GM should:

- Update inventory when:
  - Player picks up / loses items
- Use stats to:
  - Adjust outcomes (e.g., “you’re strong, so you succeed more easily”)
- Be able to **answer questions** like:
  - “What do I have in my bag?”
  - “How much health do I have left?”

Frontend bonus: show a simple **Character panel** that reflects this JSON.

---

### 3. Simple Mechanics: Checks and Dice Rolls

> **Goal:** Add light game mechanics that make decisions more interesting than pure storytelling.

Ideas:

- Add `diceRoll` logic in Python (e.g., random number 1–20).
- When the player attempts something risky:
  - Perform a roll + apply modifiers from attributes.
  - Decide outcome tier: Fail / Partial success / Full success.
- Let the GM describe the outcome accordingly.

You can either:

- Keep dice purely backend and let GM describe results, **or**
- Show the dice roll in the UI (e.g., “Roll: 14 (Success)”).

---

### 4. Multiple Universes via System Message Presets

> **Goal:** Let the player choose the universe and swap the GM’s behavior accordingly.

At the start of the game (or from a settings panel):

- Let user pick from a few **preset universes**:
  - “Classic fantasy”
  - “Cyberpunk city”
  - “Space opera”
- Each universe:
  - Uses a different system prompt.
  - Optionally initializes a different **baseline JSON world template**.


---

### 5. Save & Resume Game

> **Goal:** Allow exporting and re-importing the JSON world state so a game can be resumed later.\*\*

This is primarily an engineering challenge, not an LLM one:

- Add a “Save Game” button:
  - Serializes the JSON world state and (optionally) last few messages.
  - Maybe just download as a `.json` file or keep it in localStorage.
- Add a “Load Game” button:
  - Restores that JSON into memory.
  - Tells the GM what happened so far (through a short summary or direct JSON).

Even a very rough implementation here is impressive.

-----

- Step 1: You only need the **primary goal** to complete Day 8; the **Advanced Goals** are for going the extra mile.
- Step 2: **Successfully connect to Voice Game Master (D&D-Style Adventure)** in your browser and talk through game scenario.
- Step 3: **Record a short video** of your session with the agent.
- Step 4: **Post the video on LinkedIn** with a description of what you did for the task on Day 8. Also, mention that you are building voice agent using the fastest TTS API - Murf Falcon. Mention that you are part of the **“Murf AI Voice Agent Challenge”** and don't forget to tag the official Murf AI handle. Also, use hashtags **#MurfAIVoiceAgentsChallenge** and **#10DaysofAIVoiceAgents**

Once your agent is running and your LinkedIn post is live, you’ve completed Day 8.