# Day 6 – Fraud Alert Voice Agent

## Overview

Build a **fraud alert voice agent** for your favorite bank.

For the **primary goal**, everything can run using your existing voice setup (no extra UI):

- You will create a **sample database** describing for a few suspicious transaction. 

```json
{
  "userName" : "John",
  "securityIdentifier" : "12345",
  "cardEnding": "4242",
  "case": "safe/fraudulent",
  "transactionName" : "ABC Industry",
  "transactionTime" : "",
  "transactionCategory" : "e-commerce",
  "transactionSource" : "alibaba.com"
}

```
- When a “fraud alert” call/session starts, your agent will **use userName from the database** and:
  - Introduce itself as the bank’s fraud department.
  - Verify the customer in a basic, safe way.
  - Read out the suspicious transaction.
  - Ask if it was actually made by the customer.
  - Mark the case as **safe** or **fraudulent**.
- If you persist anything, you’ll do it by **writing to database entry**.

For the **advanced goals**, the main challenge is:

- Implement the same fraud flow using **actual telephony with LiveKit Telephony**, so someone can talk to the fraud bot from a real phone call.

You can add more advanced behavior on top if you like (multiple fraud cases, DTMF input, JSON-based “fraud ops” records, etc.).

> ⚠️ **Important:**  
> Use only **fake data**.  
> Do **not** request or handle real card numbers, PINs, passwords, or other sensitive information.  
> Keep everything clearly demo/sandbox-only.

---

## What You’ll Work With

You will typically have:

- One or more **Database entries**:
  - Input: fraud case(s) to investigate.
  - Output (optional): updated fraud case(s) or a log file reflecting results.
- Logging (e.g. terminal logs) to help you see what’s happening.

There is **no UI requirement** for this task.  
Anything you want to persist should be stored in database.

---

## Primary Goal (MVP) – Single Fraud Case from Database, In-App Call

**Objective:**  
Build a voice agent that, when a fraud alert call starts, reads a **single fraud case** from a Database, talks the user through the details, asks if the transaction is legitimate, and updates the case status in Database to safe or fraudulent.

### Tasks

1. **Create a sample fraud cases in Database**

   - Create few entries that represents **one suspicious transaction**.
   - Include at least:
     - Customer name (fake).
     - Security Identifier (fake)
     - Masked card number (e.g. `**** 1234`).
     - Transaction amount (fake).
     - Merchant name (fake).
     - Location (fake).
     - Timestamp (fake).
     - A simple security question and answer (for basic verification; fake).
     - Current status (e.g. `pending_review`).
   - Use these entries to load the fraud case at call start with username.
   - 
2. **Set up the fraud agent persona**

   - Make the agent behave like a **fraud detection representative** for a fictional bank.
   - It should:
     - Clearly introduce the bank and itself at the start of the call/session.
     - Explain that it is contacting the user about a suspicious transaction.
     - Use calm, professional, reassuring language.
   - It must **not** ask for full card numbers, PINs, or credentials. Any identity confirmation should come from non-sensitive fields in your database (e.g. a basic security question).

3. **Load the fraud case at call start**

   - When the fraud call/session begins:
     - Load the fraud case from your database after asking for username.
     - Keep this case in your scenario’s state for the duration of the call.
     - The agent should use this data to describe:
       - The merchant,
       - The amount,
       - The masked card,
       - The approximate time and location.

4. **Implement a simple call flow**

   Design a clear, minimal sequence:

   - Greet the user and explain why the bank is calling.
   - Ask a **basic verification question** (using data), such as:
     - A security question stored in the database, or
     - Confirming a non-sensitive detail.
   - If verification passes:
     - Read out the suspicious transaction details from the database entry.
     - Ask the user if they made this transaction (yes/no).
   - If verification fails:
     - Politely say that you cannot proceed and end the call.
   - Based on the yes/no answer:
     - If the user **confirms** the transaction → mark it as safe.
     - If the user **denies** the transaction → mark it as fraudulent and describe the action (e.g. card blocked, dispute raised — all mock).
   - End the call with a short confirmation of what action was taken.

5. **Update the fraud case in database**

   - After the call logic completes:
     - Update the fraud case data in database:
       - Set status to something like `confirmed_safe`, `confirmed_fraud`, or `verification_failed`.
       - Add a short outcome note (e.g. “Customer confirmed transaction as legitimate.”).
     - Write the updated fraud case back to **the database**:
       - You can overwrite the original entry.
   - Optionally log the final status and note in the console for easier debugging.

### MVP Completion Checklist

You’ve finished the **primary goal** if:

- You created a database entry describing one fake fraud case.
- When the call/session starts, the agent:
  - Loads this database entry,
  - Uses it to drive the conversation.
- The agent:
  - Introduces itself as a bank fraud rep,
  - Performs simple, safe verification,
  - Reads out the suspicious transaction,
  - Asks if the user made it,
  - Chooses the appropriate branch.
- At the end, the fraud case’s status and a short outcome summary are written back to database.

#### Resources
- https://docs.livekit.io/agents/build/prompting/
- https://docs.livekit.io/agents/build/tools/
- https://www.geeksforgeeks.org/python/python-sqlite/
- https://www.mongodb.com/resources/languages/python

---

## Advanced Goals (Optional, Higher Impact)

The main advanced goal for Day 6 is to implement this as **real telephony** using **LiveKit Telephony**, so that a real phone call can drive the same fraud-case reading and updating.

You can add other enhancements on top.

---

### Advanced Goal – Live Telephony with LiveKit Telephony

**Objective:**  
Run your fraud alert agent over a **real phone call** via [LiveKit Telephony](https://docs.livekit.io/agents/start/telephony/), with fraud cases loaded from database and results persisted back to database.

**Tasks:**

- Integrate **LiveKit Telephony** with your app:
  - Configure a phone number or telephony entry point.
  - Route incoming or outgoing calls into your Day 6 fraud scenario.
- Ensure that when a call starts:
  - A fraud case is loaded from your database entry using username.
  - The same call flow from the primary goal is used:
    - Introduction,
    - Basic verification,
    - Suspicious transaction explanation,
    - Yes/no confirmation,
    - Status update.
- When the call ends:
  - Update the fraud case status and outcome in memory.
  - Persist the changes by writing them back to database.
- Use logs to confirm:
  - Which fraud case was used,
  - What decision was made,
  - What the final status in the database is

After this, you should be able to:

- Make/receive a call,
- Talk to the fraud bot by phone,
- See the updated database reflecting the outcome of the call.

### Resources
- https://docs.livekit.io/agents/start/telephony/
- https://docs.livekit.io/sip/cloud/phone-numbers/
- https://docs.livekit.io/sip/quickstarts/configuring-plivo-trunk/
-----

- Step 1: You only need the **primary goal** to complete Day 6; the **Advanced Goals** are for going the extra mile.
- Step 2: **Successfully connect to Fraud Alert Voice Agent** in your browser and go through fraud verification scenarios of `confirmed_safe`, `confirmed_fraud`, and `verification_failed`.
- Step 3: **Record a short video** of your session with the agent and show the updated database on verification process.
- Step 4: **Post the video on LinkedIn** with a description of what you did for the task on Day 6. Also, mention that you are building voice agent using the fastest TTS API - Murf Falcon. Mention that you are part of the **“Murf AI Voice Agent Challenge”** and don't forget to tag the official Murf AI handle. Also, use hashtags **#MurfAIVoiceAgentsChallenge** and **#10DaysofAIVoiceAgents**

Once your agent is running and your LinkedIn post is live, you’ve completed Day 6.