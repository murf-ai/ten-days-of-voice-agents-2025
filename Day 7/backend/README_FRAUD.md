# Fraud Agent

This file documents how to run the `FraudAgent` within this backend.

## Overview

- The fraud agent is implemented in `src/fraud_agent.py`.
- It reads and writes `fraud_cases.json` in the backend root directory.
- The agent runs using `uv` CLI similarly to the existing wellness agent.

## Run (console)

To run the fraud agent interactively in the console (local dev):

1. Ensure backend environment file: `backend/.env.local` contains your LiveKit and other keys.
2. Install dependencies and sync: `uv sync` from backend directory.
3. Download plugin/model files (if needed):

```powershell
cd backend
uv run python src/fraud_agent.py download-files
```

4. Run the agent for the console:

```powershell
uv run python src/fraud_agent.py console
```

To run the agent normally (connect to frontend or telephony):

```powershell
uv run python src/fraud_agent.py dev
```

## File: `fraud_cases.json`

- Contains a list of sample cases. Each case includes `userName`, `securityIdentifier`, `masked card` ending, `amount`, `transactionName`, and a `securityQuestion`/`securityAnswer` used for verification.
- Cases are updated in-place and saved back to this file after the checks.
