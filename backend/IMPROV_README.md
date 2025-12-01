Improv Battle - State Server

A lightweight HTTP server is embedded in `backend/src/agent.py` to expose Improv Battle session state for tooling or the frontend to poll.

Endpoints

- GET /health
  - Returns: {"ok": true}

- GET /improv/state/{room}
  - Returns the `improv_state` dict for the given room (registered when the agent session starts).
  - Example: `http://localhost:9001/improv/state/voice_assistant_room_1234`
  - 404 if the room is not found.

- POST /improv/stop/{room}
  - Marks the session `phase` as `done` for graceful early exit.
  - Returns: {"ok": true} on success, 404 if room not found.

Configuration

- The server listens on port `9001` by default. Override by setting environment variable `IMPROV_STATE_PORT`.

Notes

- The `SESSIONS` mapping is populated in `entrypoint()` when a session starts:
  ```py
  SESSIONS[ctx.room.name] = session.userdata.improv_state
  ```
- The HTTP server is intentionally lightweight and has no auth; use only in local or trusted environments. For production, add authentication and stricter access controls.

Next steps

- Add a Next.js API route that proxies requests to this state server for browser-friendly CORS handling.
- Secure the server (add tokens or restrict to localhost) before exposing to the public internet.
