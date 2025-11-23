#!/bin/bash

# Start all services in background
livekit-server --dev &
(cd backend && uv run python src/agent_barista.py dev) &
(cd frontend && pnpm dev) &

# Wait for all background jobs
wait