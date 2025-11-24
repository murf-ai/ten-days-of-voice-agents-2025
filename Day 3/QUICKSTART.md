# Day 3 - Quick Start Guide

## 🚀 Get Started in 3 Steps

### Step 1: Start the Backend
```bash
cd backend
uv run python src/agent.py dev
```

Wait for the message: `Agent ready` or `Connected to LiveKit`

### Step 2: Start the Frontend
Open a new terminal:
```bash
cd frontend
pnpm dev
```

Wait for: `Ready on http://localhost:3000`

### Step 3: Talk to Alex from Cult.fit
1. Open your browser to `http://localhost:3000`
2. Click **"Start call"**
3. Say "Hello" and Alex will introduce themselves from Cult.fit
4. Have a wellness check-in conversation!

## 💬 What to Say

### Example Opening
**You:** "Hello"

**Alex:** "Hi, I'm Alex from Cult.fit. How are you feeling today?"

### Share Your Mood
**You:** "I'm feeling good, a bit tired though"

**Alex:** "Got it, you're feeling good. I've noted that. What's your energy like today?"

### Continue the Check-in
The agent will guide you through:
- ✅ Mood and energy levels
- ✅ Stress factors or concerns
- ✅ Daily objectives (1-3 things you want to accomplish)
- ✅ Simple, practical advice
- ✅ Recap and confirmation

## 📊 View Your Check-in History

After your first check-in, a file will be created:
```
backend/wellness_log.json
```

Open this file to see all your check-in history in JSON format.

## 🔄 Try Multiple Check-ins

The agent remembers your previous check-ins! Try:

1. Complete a check-in
2. Refresh the page or restart
3. Start a new call
4. Alex will reference your last check-in!

Example:
> "Last time we talked, you mentioned being low on energy. How does today compare?"

## 🧪 Run Tests

Verify everything works:
```bash
cd backend
uv run pytest
```

All tests should pass ✅

## 📝 Check-in Data Structure

Each check-in saves:
- **Date & Time** - When the check-in happened
- **Mood** - How you're feeling
- **Energy** - Your energy level
- **Stress Factors** - What's on your mind
- **Objectives** - Your 1-3 daily goals
- **Summary** - AI-generated recap

## 🎯 Tips for Best Experience

1. **Be conversational** - Talk naturally, like you would to a friend
2. **One topic at a time** - The agent asks one question at a time
3. **Be specific** - Share real objectives and feelings
4. **Confirm the recap** - Make sure the summary is accurate
5. **Try multiple sessions** - See how the agent remembers your history

## ⚠️ What Alex Won't Do

Alex is a wellness companion, NOT a medical professional:
- ❌ No medical diagnosis
- ❌ No medical treatment advice
- ❌ No prescription recommendations

Alex WILL:
- ✅ Listen and support
- ✅ Offer practical wellness tips
- ✅ Help you set daily goals
- ✅ Suggest simple activities (walks, breaks, etc.)

## 🐛 Troubleshooting

### Agent not responding?
- Check that backend is running (`uv run python src/agent.py dev`)
- Check that all API keys are set in `backend/.env.local`

### Can't hear the agent?
- Check browser microphone permissions
- Check speaker/headphone volume
- Try refreshing the page

### Check-ins not saving?
- Check backend terminal for errors
- Verify `backend/wellness_log.json` is created
- Check file permissions in the backend directory

## 📚 Learn More

See the full [Day 3 README](./README.md) for:
- Complete feature list
- Technical implementation details
- Data schema documentation
- Example conversations

