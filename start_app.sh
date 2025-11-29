#!/bin/bash

# Start all services in background
livekit-server --dev &
# To run any other agent, just change the file name or location below here:
(cd backend && uv run python src/agent_fraud.py dev) &
(cd frontend && pnpm dev) &

# Wait for all background jobs
wait