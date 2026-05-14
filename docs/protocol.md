# Wire protocol — v0

Goal: a stable enough wire format that the agent and the Android app can be built in parallel against this doc, without churn. All messages are JSON. WebSocket frames are one JSON object per text frame.

Version field on every frame so we can roll forward without breaking clients.

## Auth & transport

| Endpoint | Auth | Direction |
|---|---|---|
| `POST /auth/device/register` | one-time device registration token (printed by `scripts/make_device_token.py`) | phone → server |
| `POST /auth/refresh` | refresh token | phone → server |
| `GET /mashpia/setup/{token}` | single-use mashpia token | browser → server |
| `POST /mashpia/setup/{token}` | single-use mashpia token | browser → server |
| `WS /ws/phone?token=<jwt>` | short-lived access JWT | phone ↔ server |
| `WS /ws/agent` | `Authorization: Bearer <api_key>` header | agent ↔ server |

Access JWTs: 15 min. Refresh tokens: 30 days, rotating.

## Common envelope

```json
{
  "v": 0,
  "type": "<message-type>",
  "ts": "2026-05-14T12:34:56Z",
  "id": "<uuid, optional>",
  "...": "type-specific payload"
}
```

Server-side every inbound frame is validated against a pydantic model named after the `type`. Unknown types → close code 4001.

## Phone ↔ server

### Phone → server

| `type` | Payload | Meaning |
|---|---|---|
| `subscribe` | `{}` | Replay current snapshot of all lanes, then stream updates |
| `answer_question` | `{question_id, choice_index}` | Answer a pending multiple-choice question |
| `git_op` | `{lane_id, op, args?}` (see Git ops) | Request a whitelisted git op |
| `request_zal_override` | `{reason: "friday" \| "secular_holiday" \| "chabad_holiday"}` | Server checks calendar, replies with `zal_override_result` |
| `emergency_action` | `{lane_id?, action, pin}` | Approve an emergency-mode action |
| `request_freeform_unlock` | `{minutes, pin}` | Mashpia-approved limited terminal unlock (max minutes capped by mashpia config) |
| `ping` | `{}` | Keepalive |

### Server → phone

| `type` | Payload | Meaning |
|---|---|---|
| `lane_snapshot` | `{lanes: [Lane, ...]}` | Sent after `subscribe`, contains full state |
| `lane_update` | `Lane` | One lane changed |
| `lane_removed` | `{lane_id}` | Lane aborted/cleaned up |
| `question` | `Question` | New supervisor question for a lane |
| `question_resolved` | `{question_id}` | Question expired/cancelled |
| `emergency_summary` | `{lane_id, summary_md, options: [{key, label, description}]}` | LLM-generated rabbi-readable summary + action menu |
| `zal_override_result` | `{granted: bool, until: ISO, reason}` | Calendar-verified or denied |
| `freeform_unlock_result` | `{granted: bool, until: ISO, session_id?}` | Returns a constrained-terminal session if granted |
| `notification` | `{title, body, lane_id?, severity}` | Equivalent of an FCM push (in step 1 just delivered over WS) |
| `ack` | `{ref_id}` | Acks a phone-side message id |
| `error` | `{code, message, ref_id?}` | |
| `pong` | `{}` | |

## Agent ↔ server

### Agent → server

| `type` | Payload |
|---|---|
| `register` | `{agent_id, hostname, lane_capacity, agent_version}` |
| `lane_state` | `Lane` |
| `lane_removed` | `{lane_id}` |
| `question_ask` | `Question` (without `id`; server assigns) |
| `git_op_result` | `{op_id, ok, output?, error?}` |
| `freeform_session_event` | `{session_id, kind: "started" \| "output" \| "ended", data?}` |
| `heartbeat` | `{}` |

### Server → agent

| `type` | Payload |
|---|---|
| `welcome` | `{server_version, max_lanes}` |
| `question_answered` | `{question_id, choice_index}` |
| `git_op_request` | `{op_id, lane_id, op, args?}` |
| `emergency_command` | `{lane_id?, action: "kill_all" \| "pause_lane" \| "noop"}` |
| `start_freeform_session` | `{session_id, lane_id, max_minutes}` |
| `stop_freeform_session` | `{session_id}` |

## Core models

### Lane

```json
{
  "id": "uuid",
  "agent_id": "uuid",
  "branch": "feat/foo",
  "worktree_path": "/home/user/iyidden-kf/worktrees/foo",
  "last_commit": { "sha": "abc1234", "message": "fix: bar", "ts": "ISO" } ,
  "tests": { "status": "green" | "yellow" | "red" | "unknown", "summary": "string" },
  "claude_activity": "string, <=120 chars — one-liner",
  "health": "green" | "yellow" | "red",
  "idle_since": "ISO or null",
  "pending_question_id": "uuid or null",
  "updated_at": "ISO"
}
```

### Question

```json
{
  "id": "uuid",
  "lane_id": "uuid",
  "prompt": "string, <=400 chars",
  "options": ["string", "..."],
  "created_at": "ISO",
  "answered_at": "ISO or null",
  "answered_choice_index": "int or null"
}
```

## Git ops (whitelist)

| `op` | `args` | Effect |
|---|---|---|
| `view_log` | `{limit?: int}` | Returns commit log (read) |
| `view_diff` | `{sha?: str}` | Returns diff for sha or HEAD |
| `merge_to_main` | `{}` | Requires lane.tests.status == "green"; refuses otherwise |
| `revert_last_commit` | `{}` | `git revert HEAD --no-edit` |
| `abort_lane` | `{}` | Reset to main, drop worktree |
| `switch_branch` | `{branch}` | Branch must already exist; no checkout -b |

## Error codes

| Code | Meaning |
|---|---|
| `4001` | Unknown message type |
| `4002` | Invalid payload |
| `4010` | Auth required / failed |
| `4030` | Operation not allowed (e.g. merge with red tests) |
| `4040` | Resource not found |
| `4290` | Rate-limited |
| `5000` | Internal error |

## Versioning

`v: 0` until any of the above shapes change in a breaking way. On a breaking change, bump `v`, server keeps `v=0` handler around for one release before deletion. Additive changes (new `type`, new optional field) do not bump `v`.
