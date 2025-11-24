# Day 3 - Troubleshooting Guide

## Common Issues and Solutions

### 1. Agent Doesn't Introduce as "Alex from Cult.fit"

**Symptoms:**
- Agent says generic greeting
- Doesn't mention Cult.fit

**Solutions:**
- ✅ Check that you're using the updated `agent.py` from Day 3
- ✅ Restart the backend agent
- ✅ Clear any cached models: `rm -rf backend/__pycache__`
- ✅ Verify the system prompt in `WellnessAgent.__init__()`

**Verify:**
```bash
cd backend
grep -n "Cult.fit" src/agent.py
# Should show multiple matches in the system prompt
```

### 2. Check-ins Not Saving to JSON

**Symptoms:**
- No `wellness_log.json` file created
- File exists but empty
- New check-ins not appearing

**Solutions:**
- ✅ Check backend terminal for errors
- ✅ Verify write permissions in `backend/` directory
- ✅ Ensure `save_checkin()` tool is being called
- ✅ Check that all required fields are filled

**Debug:**
```bash
# Check if file exists
ls -la backend/wellness_log.json

# Check file permissions
chmod 644 backend/wellness_log.json

# View backend logs
cd backend
uv run python src/agent.py dev
# Look for "Wellness check-in saved" message
```

### 3. Agent Doesn't Reference Previous Check-ins

**Symptoms:**
- Agent acts like first conversation every time
- No mention of previous mood/energy

**Solutions:**
- ✅ Verify `wellness_log.json` has data
- ✅ Check that `get_last_checkin()` is working
- ✅ Restart the agent to reload history
- ✅ Verify system prompt includes context

**Test:**
```python
# In Python console
from pathlib import Path
import json

log_file = Path("backend/wellness_log.json")
if log_file.exists():
    with open(log_file) as f:
        data = json.load(f)
        print(f"Found {len(data)} check-ins")
        if data:
            print(f"Last check-in: {data[-1]}")
```

### 4. Agent Provides Medical Advice

**Symptoms:**
- Agent diagnoses conditions
- Suggests medical treatments
- Acts like a doctor

**Solutions:**
- ✅ This should NOT happen with the Day 3 implementation
- ✅ Verify you're using the correct system prompt
- ✅ Check that instructions include "NEVER diagnose or give medical advice"
- ✅ Report specific examples for prompt refinement

**Expected Behavior:**
- Agent should redirect to healthcare professionals
- Offer general wellness support only
- Avoid any diagnostic language

### 5. Backend Won't Start

**Symptoms:**
- Error when running `uv run python src/agent.py dev`
- Import errors
- Module not found

**Solutions:**
- ✅ Ensure you're in the `backend/` directory
- ✅ Run `uv sync` to install dependencies
- ✅ Check Python version: `python --version` (should be 3.9+)
- ✅ Verify `.env.local` has all required API keys

**Required API Keys:**
```bash
# In backend/.env.local
LIVEKIT_URL=wss://...
LIVEKIT_API_KEY=...
LIVEKIT_API_SECRET=...
MURF_API_KEY=...
GOOGLE_API_KEY=...
DEEPGRAM_API_KEY=...
```

### 6. Frontend Can't Connect

**Symptoms:**
- "Connection failed" error
- Can't start call
- No audio

**Solutions:**
- ✅ Ensure backend is running first
- ✅ Check that frontend `.env.local` matches backend
- ✅ Verify LiveKit credentials are correct
- ✅ Check browser console for errors

**Debug:**
```bash
# Check backend is running
curl http://localhost:8080/health
# or check the terminal for "Agent ready"

# Check frontend is running
curl http://localhost:3000
# Should return HTML
```

### 7. Tests Failing

**Symptoms:**
- `pytest` shows failures
- Import errors in tests
- Assertion errors

**Solutions:**
- ✅ Ensure you updated `test_agent.py` for Day 3
- ✅ Check that `WellnessAgent` is imported correctly
- ✅ Run tests from `backend/` directory
- ✅ Install test dependencies: `uv sync`

**Run Tests:**
```bash
cd backend
uv run pytest -v
# Should show 3 passing tests
```

### 8. JSON File Corrupted

**Symptoms:**
- JSON parse errors
- Agent crashes on startup
- Invalid JSON format

**Solutions:**
- ✅ Validate JSON: `python -m json.tool backend/wellness_log.json`
- ✅ Backup and recreate: `mv wellness_log.json wellness_log.backup.json`
- ✅ Let agent create new file on next check-in
- ✅ Fix manually if needed (must be valid JSON array)

**Valid Format:**
```json
[
  {
    "date": "2025-11-24",
    "timestamp": "2025-11-24T10:30:00.123456",
    "mood": "good",
    "energy": "high",
    "stress_factors": "none",
    "objectives": ["task 1"],
    "summary": "summary text"
  }
]
```

### 9. Voice Not Working

**Symptoms:**
- Can't hear agent
- Agent can't hear user
- Audio cutting out

**Solutions:**
- ✅ Check browser microphone permissions
- ✅ Check speaker/headphone volume
- ✅ Try different browser (Chrome recommended)
- ✅ Check Murf API key is valid
- ✅ Check Deepgram API key is valid

**Browser Permissions:**
1. Click lock icon in address bar
2. Allow microphone access
3. Refresh page
4. Try again

### 10. Slow Response Times

**Symptoms:**
- Long delays between user speech and agent response
- Agent takes forever to respond

**Solutions:**
- ✅ Check internet connection
- ✅ Verify API rate limits not exceeded
- ✅ Check backend logs for errors
- ✅ Ensure `preemptive_generation=True` in agent config

**Performance Tips:**
- Use wired internet connection
- Close other bandwidth-heavy applications
- Check API service status pages

## Getting Help

### Check Logs
```bash
# Backend logs
cd backend
uv run python src/agent.py dev
# Watch for errors in red

# Frontend logs
cd frontend
pnpm dev
# Check browser console (F12)
```

### Verify Installation
```bash
# Check all dependencies
cd backend
uv sync
uv run pytest

cd frontend
pnpm install
pnpm build
```

### Reset Everything
```bash
# Nuclear option - start fresh
cd backend
rm -rf __pycache__ .pytest_cache wellness_log.json
uv sync

cd frontend
rm -rf .next node_modules
pnpm install
```

## Still Having Issues?

1. Check the main [README](./README.md) for setup instructions
2. Review the [QUICKSTART](./QUICKSTART.md) guide
3. Compare your code with the [CHANGES](./CHANGES.md) document
4. Check the example data in `wellness_log_example.json`

