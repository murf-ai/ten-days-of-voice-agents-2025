# Day 4 – Teach-the-Tutor: Active Recall Coach

For Day 4, you’ll turn the agent into an **active recall coach** that learns from the user and tracks **concept-level mastery** as the user teaches concepts back to it.

The core idea: **the best way to learn is to teach** – so the agent explains topics, quizzes you, then asks _you_ to explain them back and scores how well you did.

---

### Primary Goal (Required)

Keep this simple and focused: build a “Teach-the-Tutor” experience with three modes using a small content file.

- **Three learning modes**

  - `learn` – the agent explains a concept. (With Murf Falcon Voice - "Matthew")
  - `quiz` – the agent asks you questions. (With Murf Falcon Voice - "Alicia" )
  - `teach_back` – the agent asks _you_ to explain the concept back (and gives basic qualitative feedback). (With Murf Falcon Voice - "Ken")

- **Small course content file**
  - Add a small JSON file (e.g. `shared-data/day4_tutor_content.json`) with a few concepts:

```json
[
  {
    "id": "variables",
    "title": "Variables",
    "summary": "Variables store values so you can reuse them later...",
    "sample_question": "What is a variable and why is it useful?"
  },
  {
    "id": "loops",
    "title": "Loops",
    "summary": "Loops let you repeat an action multiple times...",
    "sample_question": "Explain the difference between a for loop and a while loop."
  }
]
```

- Use this file to:

  - Explain concepts in **Learn** mode (via `summary`).
  - Pick basic quiz / teach-back prompts (via `sample_question`).

**You complete Day 4** when:

- The agent first greets the user, asks for their preferred learning mode, and then connects them to the correct voice agent.
- All three modes — **learn, quiz, and teach_back** — are fully supported and driven by your JSON content.
- The user can switch between learning modes at any time by simply asking to switch.
- In each mode, the agent correctly uses the content file: explaining in learn, asking questions in quiz, and prompting the user to teach back in teach_back.

#### Resources:
- https://docs.livekit.io/agents/build/agents-handoffs/#tool-handoff
- https://docs.livekit.io/agents/build/agents-handoffs/#context-preservation
- https://github.com/livekit-examples/python-agents-examples/blob/main/complex-agents/medical_office_triage/triage.py

---

### Advanced Challenge (Optional)

For participants who want to go beyond the basics, you can push the “active recall coach” idea much further. This is **not required** to complete Day 4.

Ideas (pick one or more):

#### **1. Richer concept mastery model (backend)**
  - Upgrade your `tutor` state to track scores and averages per concept, e.g.:

```python
session_state["tutor"]["mastery"]["loops"] = {
    "times_explained": 3,
    "times_quizzed": 4,
    "times_taught_back": 2,
    "last_score": 72,   # 0–100
    "avg_score": 65.3,  # running average
}
```

#### Resources:
- Use a Database: https://www.geeksforgeeks.org/python/python-sqlite/

#### **2. Teach-back evaluator tool**
  - Implement a helper that the agent calls to _score_ explanations based on the concept summary:

```python
result = tools.evaluate_teach_back(
    concept_summary=concept_summary,
    user_explanation=user_explanation,
)
# result["score"] (0–100), result["feedback"] (1–2 sentences)
```

- Use this to update `last_score` / `avg_score` and give targeted feedback.
- Let the user ask “Which concepts am I weakest at?” and answer from these scores.

#### Resources:
- Use a Database: https://www.geeksforgeeks.org/python/python-sqlite/

#### **3. Richer content & flows**
  - Add more concepts and lightweight “learning paths” (beginner → intermediate → advanced).
  - Let the agent propose a practice plan based on the weakest concepts.

#### Resources:
- Use a Document Database for content with tags: https://www.mongodb.com/

These advanced pieces are for extra challenge and polish; **only the Primary Goal is required** for a Day 4 pass.

-----

- Step 1: You only need the **primary goal** to complete Day 4; the **Advanced Goals** are for going the extra mile.
- Step 2: **Successfully connect to the Teach-the-Tutor: Active Recall Coach** in your browser and use all the three learning modes (`learn`, `quiz` and `teach_back`)
- Step 3: **Record a short video** of your session with the agent using all the three learning modes.
- Step 4: **Post the video on LinkedIn** with a description of what you did for the task on Day 4. Also, mention that you are building voice agent using the fastest TTS API - Murf Falcon. Mention that you are part of the **“Murf AI Voice Agent Challenge”** and don't forget to tag the official Murf AI handle. Also, use hashtags **#MurfAIVoiceAgentsChallenge** and **#10DaysofAIVoiceAgents**

Once your agent is running and your LinkedIn post is live, you’ve completed Day 4.
