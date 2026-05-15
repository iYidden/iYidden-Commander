# iYidden Commander — backend (step 1)

FastAPI service. Rendezvous between the dev-machine agent and the phone.

## What's in step 1

- HTTP auth: device registration with single-use tokens, JWT access tokens, rotating refresh tokens
- Mashpia setup flow: single-use HTML page protected by a 24h token, sets the 6-digit PIN, 12-char backup password, and `max_freeform_minutes`
- WebSocket endpoints `/ws/phone` (JWT auth) and `/ws/agent` (API-key auth)
- In-process lane store with pub/sub fan-out to all connected phones
- Agent registry — phones can issue git ops / answers that the server forwards to the right agent
- Stubbed LLM client; real Anthropic calls land in step 8
- SQLite persistence for durable state (devices, tokens, mashpia config, emergency-event audit log)

What's NOT here (intentionally): real git ops, real LLM calls, FCM, calendar-aware zal override, emergency-mode flow. All stubbed; protocol shapes are locked in [`../docs/protocol.md`](../docs/protocol.md) so steps 2-3 don't churn.

## Run locally

```bash
cd backend
cp .env.example .env
# generate two random secrets:
python -c "import secrets; print('JWT_SECRET=' + secrets.token_urlsafe(48))"
python -c "import secrets; print('AGENT_API_KEY=' + secrets.token_urlsafe(32))"
# paste both into .env

uv sync
uv run uvicorn iyidden_backend.main:app --host 0.0.0.0 --port 443 --reload
```

## Smoke test

In another shell — from `backend/`:

### 1. Health
```bash
curl -s http://localhost:443/health
# {"ok":true,"lanes":0,"agents":0,"subscribers":0}
```

### 2. Mashpia setup link
```bash
uv run python scripts/make_mashpia_token.py
# prints: http://localhost:443/mashpia/setup/<long-token>
```
Open the URL in a browser → set PIN `123456`, backup password `correct horse battery staple`, max 10 minutes → submit. Re-opening the URL should now 404 (single-use).

```bash
curl -s http://localhost:443/mashpia/status
# {"configured":true,"max_freeform_minutes":10}
```

### 3. Register a device, hit /lanes
```bash
TOKEN=$(uv run python scripts/make_device_token.py "test phone" | tail -1)

curl -s -X POST http://localhost:443/auth/device/register \
  -H 'content-type: application/json' \
  -d "{\"registration_token\":\"$TOKEN\",\"label\":\"test\"}"
# {"access_token":"...","refresh_token":"...","device_id":"..."}

ACCESS=...   # paste the access_token
curl -s http://localhost:443/lanes -H "Authorization: Bearer $ACCESS"
# []
```

### 4. WebSocket round-trip (websocat required)

Terminal A — fake agent:
```bash
websocat -H 'Authorization: Bearer <AGENT_API_KEY from .env>' ws://localhost:443/ws/agent
# you should see: {"v":0,"type":"welcome",...}
# now send a register, then a lane:
{"v":0,"type":"register","agent_id":"agent-1","hostname":"laptop","lane_capacity":3,"agent_version":"0.1.0"}
{"v":0,"type":"lane_state","lane":{"id":"lane-1","agent_id":"agent-1","branch":"feat/foo","worktree_path":"/tmp","tests":{"status":"green","summary":"42 passed"},"claude_activity":"running tests","health":"green","updated_at":"2026-05-14T12:00:00Z"}}
```

Terminal B — phone:
```bash
websocat "ws://localhost:443/ws/phone?token=$ACCESS"
{"v":0,"type":"subscribe"}
# you'll see lane_snapshot containing lane-1, then live lane_update frames
```

### 5. Tests
```bash
uv run pytest -q
```
