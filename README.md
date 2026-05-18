# iYidden Commander

Android app + backend system for supervising multiple parallel Claude Code agents from a phone, with a Device-Owner "zal mode" lockdown for use during seder. Built for [iYidden](https://github.com/iYidden), authored as a tool for the founder while learning in yeshiva.

## Components

| Path | What it is |
|------|------------|
| [`backend/`](backend) | FastAPI + websockets rendezvous server. Runs on a VPS. |
| [`agent/`](agent) | Python agent that runs on the dev machine (WSL2 + tmux). Manages lanes, watches Claude Code sessions, executes safe git ops. |
| [`android/`](android) | Kotlin / Jetpack Compose phone app. The only allowed point of phone interaction. |
| [`docs/`](docs) | Architecture, protocol, Device-Owner provisioning, deployment. |

## Status

What works today:

- **Backend** — FastAPI service with `/health` and two websocket endpoints (`/ws/agent`, `/ws/phone`), deployed behind nginx + TLS on a Linux VPS.
- **Agent** — connects to the backend, authenticates with a Bearer token, registers, sends application-level heartbeats on a configurable interval, and reconnects with exponential backoff (1s → 60s cap, resets on successful re-registration).

Planned, not yet built:

- Android app (zero lines yet — directory does not exist).
- Real lane monitoring inside the agent (tmux scan, Claude Code session detection, git op execution).
- Zal-mode Device Owner provisioning.
- MCP question/answer tool.
- FCM push notifications.

## Design rules (hard)

1. **No freeform Claude input from the phone.** Period. The only exception is the time-limited emergency-mode unlock, gated by the mashpia PIN.
2. **Every phone screen must be answerable in under 60 seconds.** Phone interaction during seder is bittul Torah.
3. **Zal-mode override** requires either the mashpia PIN, or the backend verifying via calendar (Hebcal + Chabad-dates table) that today is Friday / non–Yom-Tov secular holiday / Chabad holiday.

## Quick start

### Prerequisites

- Python 3.11+
- [`uv`](https://docs.astral.sh/uv/) for dependency management
- Git
- A backend reachable over wss:// (deploy your own, or run the backend locally — see below)

### Backend (local development)

```bash
cd backend
cp .env.example .env   # then fill in any required values
uv sync
uv run uvicorn iyidden_backend.main:app --host 0.0.0.0 --port 8000 --reload
```

Smoke test:

```bash
curl http://localhost:8000/health
```

See [`backend/README.md`](backend/README.md) for the full curl + websocat walkthrough.

### Agent (local development)

The agent connects to the backend over a websocket and authenticates with a shared secret that must match `AGENT_API_KEY` on the backend.

```bash
cd agent
cp .env.example .env
```

Edit `.env`:
BACKEND_URL=wss://your-backend-host/ws/agent       # or ws://localhost:8000/ws/agent for local
AGENT_API_KEY=<must match backend's AGENT_API_KEY>
AGENT_NAME=<anything human-readable, shows up in logs>
HEARTBEAT_INTERVAL=30
LOG_LEVEL=INFO

Then:

```bash
uv sync
uv run python -m agent.main
```

### What a healthy run looks like
agent_starting   name=my-agent
connecting       agent=my-agent  url=wss://.../ws/agent
connected
registered       agent_id=my-agent  hostname=...
received         msg={'v': 0, 'type': 'welcome', 'server_version': '...', 'max_lanes': 8}

Heartbeats are sent at `HEARTBEAT_INTERVAL` and log at `DEBUG` level (silent at `INFO`). On the backend, you'll see an `agent_registered` log line; heartbeats are accepted silently — connection liveness is the signal.

If the backend goes away, the agent retries with exponential backoff:
connection_error error="..."   type=...
reconnecting_in  seconds=1   reset=False
reconnecting_in  seconds=2   reset=False
reconnecting_in  seconds=4   reset=False
...

When the backend comes back, the agent reconnects and `reset=True` appears on the next disconnect — confirming the backoff was reset on successful registration.

## Deployment

Production deployment is intentionally not documented in detail here. See [`backend/README.md`](backend/README.md) for the deployment notes that live with the backend. In short: any Linux host that can run a Python service behind nginx with TLS will work.

The agent currently runs interactively on a developer machine; running it as a long-lived service is a future concern.

## Documentation

- [`docs/SPEC.md`](docs/SPEC.md) — full architectural specification.
- [`docs/protocol.md`](docs/protocol.md) — wire protocol reference. The pydantic models in [`backend/src/iyidden_backend/models/wire.py`](backend/src/iyidden_backend/models/wire.py) are the source of truth; the agent currently hand-rolls matching JSON dicts.

## Build order

Each step is its own branch, merged after review. See [`docs/SPEC.md`](docs/SPEC.md) for full detail.

1. ✅ Backend skeleton
2. ✅ Agent skeleton (connect, register, heartbeat, reconnect)
3. Android skeleton ← current
4. Zal mode (Device Owner)
5. Real lane monitoring in the agent
6. Git GUI overlay
7. Question/answer flow (MCP tool)
8. Emergency mode
9. FCM notifications
10. Polish and production hardening

## License

(Not yet declared.)
