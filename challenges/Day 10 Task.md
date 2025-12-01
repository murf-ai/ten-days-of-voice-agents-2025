# Day 10 – Voice Improv Battle

Today you will build a **voice-first improv game show**:

---

## Game Concept: “Improv Battle”

This is not a quiz or trivia game. It is a **short-form improv performance game**.

Each round (single-player):

1. Host sets up an improv scenario  
   (e.g., “You are a barista who has to tell a customer that their latte is actually a portal to another dimension.”)
2. You (the player) act it out for a bit.
3. The host reacts:
   - Comments on what you did.
   - Might tease, critique, or praise.
   - Moves to the next scenario.

In multi-player (optional advanced goal):

- Host sets the scene.
- Player 1 starts the improv.
- Player 2 must continue the story from Player 1’s last line.
- Host reacts to how well the handoff and continuation worked.

---

## Primary Goal (Required) – Single-Player Improv Battle

Build a **single-player improv host** where:

- The user joins from the browser.
- The AI plays the role of a game show host.
- The game runs through several improv scenarios.
- The host reacts in a varied, realistic way.

### Behaviour Requirements

Your system should:

1. Let a single user join a game room from the web UI

   - Simple join screen:
     - Text field for “Name” (contestant name).
     - Button: “Start Improv Battle”.
   - On click:
     - Connect to a LiveKit voice agent.
     - Start the improv with AI host.

2. Use a strong “improv host” persona

   In your system prompt, define:

   - Role: “You are the host of a TV improv show called ‘Improv Battle’.”
   - Style:

     - High-energy, witty, and clear about rules.
     - Reactions should be **realistic**:

       - Sometimes amused, sometimes unimpressed, sometimes pleasantly surprised.
       - Not always supportive; light teasing and honest critique are allowed.
       - Stay respectful and non-abusive.

   - Structure:

     - Introduce the show and explain the basic rules.
     - Run N improv rounds (e.g., 3–5).
     - For each round:

       - Set a scenario.
       - Ask the player to improvise.
       - Once they finish, react and move on.

3. Maintain basic game state in backend

   Use a simple state object per session, for example:

   ```python
   improv_state = {
       "player_name": None,
       "current_round": 0,
       "max_rounds": 3,
       "rounds": [],  # each: {"scenario": str, "host_reaction": str}
       "phase": "intro",  # "intro" | "awaiting_improv" | "reacting" | "done"
   }
   ```

   The backend should:

   - Set `player_name` from the first answer if not provided explicitly.
   - Increment `current_round` as each scenario completes.
   - Move `phase` between `awaiting_improv` and `reacting`.

4. Generate improv scenarios and listen for player performance

   - Prepare a list of scenarios (JSON) or generate them via LLM.
   - Each scenario should be:

     - Clear: who the player is, what’s happening, what the tension is.
     - A prompt that encourages playing a character or situation.

   Examples of scenarios:

   - “You are a time-travelling tour guide explaining modern smartphones to someone from the 1800s.”
   - “You are a restaurant waiter who must calmly tell a customer that their order has escaped the kitchen.”
   - “You are a customer trying to return an obviously cursed object to a very skeptical shop owner.”

   Flow per round:

   - Host: announces the scenario and clearly tells the player to start improvising.
   - Player: responds in character.
   - When the player stops, or indicates they are done (e.g., pauses and says “Okay” or “End scene”), the host reacts.

   You can use simple heuristics for “end of scene”, such as:

   - A specific phrase (“End scene”) or
   - A maximum time / number of user turns.

5. Host reactions that feel varied and realistic

   After each scene:

   - Host should:

     - Comment on what worked, what was weird, or what was flat.
     - Mix positive and critical feedback:

       - Sometimes: “That was hilarious, especially the part where…”
       - Sometimes: “That felt a bit rushed; you could have leaned more into the character.”

   - To encourage this:

     - Add to the prompt that the host should **randomly choose** between more supportive, neutral, or mildly critical tones, while staying constructive and safe.

   Store the reaction text in `improv_state["rounds"]`.

6. Provide a short closing summary

   When `current_round` reaches `max_rounds`:

   - Host should:

     - Summarize what kind of improviser the player seemed to be:

       - Emphasis, for example, on character, absurdity, emotional range, etc.

     - Mention specific moments or scenes that stood out.
     - Thank the player and close the show.

7. Handle early exit

   - If the user clearly indicates they want to stop (e.g., “stop game”, “end show”), the host should:

     - Confirm and gracefully end the session.

If you implement all of the above, your Day 10 primary goal is complete.

#### Resources 
- https://docs.livekit.io/agents/build/prompting/
- https://docs.livekit.io/agents/build/tools/
- https://docs.livekit.io/agents/build/nodes/#on_user_turn_completed
- https://docs.livekit.io/agents/build/nodes/#on-exit
- https://docs.livekit.io/agents/build/nodes/#transcription-node

---

## Advanced Goals (Optional)

These goals introduce multi-player improv stages and richer mechanics. You can pick any subset.

---

### Advanced Goal 1 – Two-Player Relay Improv (Single Room)

Add a **multi-player mode** where two players join the same room and participate in a staged improv relay.

Target behaviour:

- Two players join a room with a shared code.
- The host:

  - Introduces both players.
  - Explains the rules:

    - Host sets the scene.
    - Player 1 starts the improv.
    - Player 2 must pick up exactly where Player 1 left off and continue.
    - Host reacts after each handoff and at the end of the scene.

- Reactions:

  - Host responds to how smooth or awkward the transition was.
  - Host is allowed to be mildly critical, surprised, or amused – not always supportive.

Implementation hints:

1. **Room joining**

   - Add a “Room Code” join flow in React:

     - Player enters name and room code.
     - Both players who enter the same code join the same LiveKit room.

2. **Player roles and state**

   In backend, maintain something like:

   ```python
   improv_state = {
       "players": {},  # identity -> {"name": str, "role": "P1"/"P2"}
       "turn_order": [],  # list of identities in order: [P1_identity, P2_identity]
       "current_round": 0,
       "phase": "intro",  # "intro" | "P1_improv" | "P2_improv" | "host_react" | "done"
       "current_scenario": None,
       "rounds": []
   }
   ```

   - Assign the first connected player as `P1`, the second as `P2`.
   - `phase` transitions:

     - `intro` → `P1_improv` → `P2_improv` → `host_react` → next round or `done`.

3. **Turn-taking and speaker attribution**

   - Use LiveKit’s participant identity to tag ASR text with the player.
   - Only accept content from the player whose turn it is:

     - During `P1_improv`, ignore or gently redirect input from P2.
     - During `P2_improv`, ignore or redirect input from P1.

   - After P1 says a cue like “passing it on” or after a time/turn limit:

     - Host explicitly hands the scene to P2:

       - “Now Player 2, pick it up from that last line and keep the story going.”

4. **Host reactions to transitions**

   - Once P2 completes their part, the host should:

     - Comment on how well P2 picked up the story from P1.
     - Highlight:

       - Continuity: did they respect what P1 established?
       - Creativity: did they add something interesting?
       - Awkwardness: if they ignored or contradicted earlier details.

   - Prompt the LLM to vary tone:

     - Sometimes complimentary, sometimes critical, sometimes mixed.
     - Always respectful and non-abusive.

   Store a short summary of each round (scenario + brief reaction) in `rounds`.

5. **Basic scoreboard (optional within this goal)**

   - You can track a simple “improv score” per player per round if you want, but it is not required for this goal.
   - If you do, consider a small numeric or qualitative scale:

     - e.g. “Strong continuity”, “Good character work”, etc.

---

### Advanced Goal 2 – Simple Scoreboard UI

Add a minimal scoreboard in the React UI:

- Show each player and:

  - Either a numeric score, or
  - A few tags like “Bold”, “Story-focused”, “Character-focused”.

- This can be a simple list component populated from:

  - A backend endpoint, or
  - Data messages from the agent.

For single-player mode:

- You can show per-round comments or strengths instead of “scores”.

#### Resources
- https://docs.livekit.io/home/client/data/text-streams/
- https://docs.livekit.io/home/client/data/rpc/
-----

- Step 1: You only need the **primary goal** to complete Day 10; the **Advanced Goals** are for going the extra mile.
- Step 2: **Successfully connect to Improv Voice Agent** in your browser and go through a few scenarios.
- Step 3: **Record a short video** of your session with the agent(host).
- Step 4: **Post the video on LinkedIn** with a description of what you did for the task on Day 10. Also, mention that you are building voice agent using the fastest TTS API - Murf Falcon. Mention that you are part of the **“Murf AI Voice Agent Challenge”** and don't forget to tag the official Murf AI handle. Also, use hashtags **#MurfAIVoiceAgentsChallenge** and **#10DaysofAIVoiceAgents**

Once your agent is running and your LinkedIn post is live, you’ve completed Day 10.