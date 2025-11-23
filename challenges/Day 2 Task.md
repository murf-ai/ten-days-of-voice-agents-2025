# Day 2 – Coffee Shop Barista Agent

For Day 2, your primary objective is to turn the starter agent into a **coffee shop barista** that can take voice orders and show a neat text summary.

### Primary Goal (Required)

- **Persona**: Turn the agent into a friendly barista for a coffee brand of your choice.
- **Order state**: Maintain a small order state object:

```json
{
  "drinkType": "string",
  "size": "string",
  "milk": "string",
  "extras": ["string"],
  "name": "string"
}
```

- **Behavior**:
  - The agent should ask clarifying questions until all fields in the order state are filled.
  - Once the order is complete, save the order to a JSON file summarizing the order.

#### Resources:
- https://docs.livekit.io/agents/build/tools/
- https://docs.livekit.io/agents/build/agents-handoffs/#passing-state
- https://docs.livekit.io/agents/build/tasks/
- https://github.com/livekit/agents/blob/main/examples/drive-thru/agent.py

Completing the above is enough to finish Day 2.

### Advanced Challenge (Optional)

This part is **completely optional** and only for participants who want an extra challenge:

- Build an **HTML-based beverage image generation system**.
- The rendered HTML “drink image” should change according to the order. For example:
  - If the order is **small**, show a small cup; if **large**, show a larger cup.
  - If the drink has **whipped cream**, visualize it with a simple HTML shape on top of the cup.
- Instead of the beverage image, you can also render an HTML order receipt.

#### Resources:
- https://docs.livekit.io/home/client/data/text-streams/
- https://docs.livekit.io/home/client/data/rpc/

-----

- Step 1: You only need the **primary goal** to complete Day 2; the **Advanced Challenge** is for going the extra mile.
- Step 2: **Successfully connect to the coffee shop barista** in your browser and place a coffee order.
- Step 3: **Record a short video** of your session placing a coffee order with the agent and show the JSON file summarizing the order.
- Step 4: **Post the video on LinkedIn** with a description of what you did for the task on Day 2. Also, mention that you are building voice agent using the fastest TTS API - Murf Falcon. Mention that you are part of the **“Murf AI Voice Agent Challenge”** and don't forget to tag the official Murf AI handle. Also, use hashtags **#MurfAIVoiceAgentsChallenge** and **#10DaysofAIVoiceAgents**

Once your agent is running and your LinkedIn post is live, you’ve completed Day 2.
