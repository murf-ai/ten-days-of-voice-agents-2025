## Primary Goal – Simple FAQ SDR + Lead Capture

**Objective:**  
Build a voice agent Sales Development Representative (SDR) that can answer basic company questions and then generate lead (potential customer details) and summary data at the end of the call.

### Tasks

1. **Pick a company**
   - Pick any Indian company/startup
   - Gather basic info (copy+paste), FAQ and pricing detail (if available) of the company in suitable format. (Text/JSON)


2. **Set up the SDR persona (Prompt Designing)**

   - Make the assistant act as an SDR for a chosen company/brand
   - It should:
     - Greet the visitor warmly.
     - Ask what brought them here and what they're working on.
     - Keep the conversation focused on understanding the user’s needs.


3. **Use the FAQ to answer questions with Agent**

   - Load the provided company content. (prepared in Step 1)
   - When the user asks product/company/pricing questions:
     - Find relevant FAQ entries (even simple keyword search is fine).
     - Answer based on that content (avoid making up details not in the FAQ).
   - The agent should be able to handle questions like:
     - “What does your product do?”
     - “Do you have a free tier?”
     - “Who is this for?”


4. **Collect lead information**

   - Decide on the key lead fields to collect, for example:
     - Name
     - Company
     - Email
     - Role
     - Use case (what they want to use this for)
     - Team size
     - Timeline (now / soon / later)
   - Make the agent naturally ask for these during the conversation.
   - Store the answers in a JSON file as the user responds.

5. **Create an end-of-call summary**
   - Detect when the user is done (e.g. they say “That’s all”, “I’m done”, “Thanks”).
   - Have the agent:
     - Give a short verbal summary of the lead (who they are, what they want, rough timeline).
   - Store the collected fields in a JSON file:
     - Name, company, email
     - Role
     - Use case
     - Team size
     - Timeline

### MVP Completion Checklist

You’ve finished the primary goal if:

- The agent clearly behaves like an SDR for a specific company/product.
- It can answer “what do you do / who is this for / pricing basics” using the FAQ content.
- It politely asks for and stores key lead details.

Only the primary goal is required to complete the challenge.

#### Resources:
- https://docs.livekit.io/agents/build/turns/vad/#prewarm (Hint - Load FAQ and preprocess)
- https://docs.livekit.io/agents/build/prompting/
- https://docs.livekit.io/agents/build/tools/
- https://github.com/livekit-examples/python-agents-examples/tree/main/rag (Advance example. You can just split the FAQ page into paragraph / JSON and do similarity search. Note - Pick any Indian company/startup)
---

## Advanced Goals (Optional, Higher Impact)

These are optional extensions. Each one makes the project more impressive and closer to a real-world SDR assistant. Pick any that you like ( or all of them if you want to go all out ).

---

### Advanced Goal 1 – Mock Meeting Scheduler

**Objective:**  
Let the SDR propose and “book” a meeting time into a fake calendar.

**Tasks:**

- Prepare a list of available time slots (mock calendar data).
- When the user asks to book a demo or meeting:
  - Offer a few available time options.
  - Let the user pick a slot by voice.
  - Confirm the chosen time back to the user.
- Keep track of the booked meeting details (date, time, lead name/email) in the to be used later.

#### Resources:
- Google Calender MCP - https://mcp.composio.dev/googlecalendar

---

### Advanced Goal 2 – CRM-Style Call Notes & Qualification Score

**Objective:**  
Generate structured notes and a simple qualification score from the conversation.

**Tasks:**

- After the call ends, process the conversation transcript and extract:
  - Key pain points.
  - Whether budget was mentioned.
  - Whether the caller seems like a decision maker, an influencer, or unknown.
  - How clear/urgent the need is.
  - Optionally refine the lead timeline (now / soon / later) you captured in the primary goal, or infer it if it wasn’t collected.
  - An overall “fit score” (e.g. 0–100).
- Store these notes in a JSON file.
- Make the notes concise and readable, like something you’d paste into a CRM.

#### Resources:
- https://docs.livekit.io/agents/build/prompting/
- https://docs.livekit.io/agents/build/nodes/#on-exit
- https://docs.livekit.io/agents/build/events/#conversation_item_added
- https://platform.openai.com/docs/guides/structured-outputs

---

### Advanced Goal 3 – Persona-Aware Pitching

**Objective:**  
Adapt the SDR’s pitch depending on who the caller seems to be.

**Tasks:**

- Implement a web search tool to get the latest information about the prospect - their company, their role, their interests, etc.
- While on call, infer a simple persona from the user’s language and self-description, for example:
  - Developer
  - Product manager
  - Founder
  - Marketer
- Create tailored pitch angles for each persona:
  - What matters most to developers?
  - What matters most to PMs?
  - Etc.
- When explaining the product, have the SDR:
  - Use the persona-specific angle and benefits.
  - Adjust examples and language based on that persona.

#### Resources:
- https://docs.livekit.io/agents/build/tools/
- https://platform.openai.com/docs/guides/tools-web-search?api-mode=chat

---

### Advanced Goal 4 – Follow-Up Email Draft

**Objective:**  
Automatically draft a follow-up email after the call.

**Tasks:**

- Use the call transcript and lead details to generate:
  - A subject line.
  - A short follow-up email body (2–3 paragraphs).
  - A clear call-to-action (e.g. reply to book a time, or link placeholder).
- Store this email draft in a JSON file.
- Make it easy to copy the draft so it could be pasted into an email client.

#### Resources:
- https://docs.livekit.io/agents/build/prompting/
- https://docs.livekit.io/agents/build/nodes/#on-exit
- https://docs.livekit.io/agents/build/events/#conversation_item_added
- https://platform.openai.com/docs/guides/structured-outputs

---

### Advanced Goal 5 – Return Visitor Recognition

**Objective:**  
Use session information to recognize repeat visitors (on the same device) and greet them differently.

**Tasks:**

- Reuse the lead information collected in the primary goal and store it in session state (e.g. based on email or name + company).
- On a new session, check if this lead already exists.
- If they are a returning lead:
  - Greet them as a returning visitor.
  - Briefly summarize what they were interested in last time.
  - Skip questions you already know the answers to (like team size or basic use case).

#### Resources:
- https://docs.livekit.io/agents/build/prompting/
- https://docs.livekit.io/agents/build/tools/
- Hint - Use a database / JSON to store previous conversation details

-----

- Step 1: You only need the **primary goal** to complete Day 5; the **Advanced Goals** are for going the extra mile.
- Step 2: **Successfully connect to SDR agent** in your browser and ask questions about company and answer questions to generate lead.
- Step 3: **Record a short video** of your session with the agent and show the generated lead and summary.
- Step 4: **Post the video on LinkedIn** with a description of what you did for the task on Day 5. Also, mention that you are building voice agent using the fastest TTS API - Murf Falcon. Mention that you are part of the **“Murf AI Voice Agent Challenge”** and don't forget to tag the official Murf AI handle. Also, use hashtags **#MurfAIVoiceAgentsChallenge** and **#10DaysofAIVoiceAgents**

Once your agent is running and your LinkedIn post is live, you’ve completed Day 5.
