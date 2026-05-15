# iYidden Commander

Android app + backend system for supervising multiple parallel Claude Code agents from a phone, with a Device-Owner "zal mode" lockdown for use during seder. Built for [iYidden](https://github.com/iYidden), authored as a tool for the founder while learning in yeshiva.

## Components

| Path | What it is |
|------|-----------|
| [`backend/`](backend) | FastAPI + websockets rendezvous server. Runs on a VPS. |
| [`agent/`](agent) | Python agent that runs on the dev machine (WSL2 + tmux). Manages lanes, watches Claude Code sessions, executes safe git ops. |
| [`android/`](android) | Kotlin / Jetpack Compose phone app. The only allowed point of phone interaction. |
| [`docs/`](docs) | Architecture, protocol, Device-Owner provisioning, deployment. |

## Design rules (hard)

1. **No freeform Claude input from the phone.** Period. The only exception is the time-limited emergency-mode unlock, gated by the mashpia PIN.
2. **Every phone screen must be answerable in under 60 seconds.** Phone interaction during seder is bittul Torah.
3. **Zal-mode override** requires either the mashpia PIN, or the backend verifying via calendar (Hebcal + Chabad-dates table) that today is Friday / non–Yom-Tov secular holiday / Chabad holiday.

## Build order

See [the spec](docs/SPEC.md). Each step is its own branch, merged after review.

1. **Backend skeleton** ← current
2. Agent skeleton (fake lane data)
3. Android skeleton
4. Zal mode (Device Owner)
5. Real lane monitoring in the agent
6. Git GUI overlay
7. Question/answer flow (MCP tool)
8. Emergency mode
9. FCM notifications
10. Polish and production hardening

## Running locally (step 1)

```bash
cd backend
uv sync
uv run uvicorn iyidden_backend.main:app --host 0.0.0.0 --port 443 --reload
```

See [`backend/README.md`](backend/README.md) for the curl/websocat smoke test.
