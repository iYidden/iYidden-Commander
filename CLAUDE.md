# CLAUDE.md — iYidden Commander

Read this before doing anything in this repo.

## What this is

A phone-first supervisor for parallel Claude Code agents running on a dev machine. Android app + FastAPI VPS backend + Python dev-machine agent. The user is a yeshiva bochur — every minute of phone interaction during seder is bittul Torah, so the product is built around minimizing his attention.

## Hard product rules — do not negotiate

1. **No freeform Claude input from the phone.** If you find yourself building a "send message to Claude" text field, stop. The only freeform path is the emergency-mode unlock, which is PIN-gated and time-limited by the mashpia.
2. **Every phone screen must be answerable in under 60 seconds.** If a flow takes longer, redesign.
3. **Zal mode is the centerpiece**, not a side feature. It locks the phone to this app on a schedule. PIN-gated by mashpia. Override allowed only when backend can verify via calendar (Hebcal + Chabad-dates table) that today is Friday / non-YT secular holiday / Chabad holiday.

## Build order

Strictly sequential. Each step is its own git branch off `main`, merged only after user review.

1. Backend skeleton (FastAPI, auth, websocket, in-memory state, stubs)
2. Dev-machine agent skeleton (fake lane data)
3. Android skeleton (lane swipe)
4. Zal mode (Device Owner, PIN, schedule)
5. Real lane monitoring (tmux + git watcher)
6. Git GUI overlay (safe-write ops only)
7. Question/answer flow (MCP `ask_supervisor`)
8. Emergency mode (rabbi-readable summaries via Anthropic API)
9. FCM notifications
10. Polish, debug-build PIN exposure, production hardening

## Stack decisions

- **Backend:** Python 3.11, `uv`, FastAPI, `websockets`, pydantic v2, aiosqlite, `python-jose`, `argon2-cffi`, `anthropic`, `structlog`.
- **Agent:** Python 3.11, runs in **WSL2 Ubuntu** on the user's Windows laptop. tmux managed via `libtmux`.
- **Android:** Kotlin, Jetpack Compose, Hilt, Room, WorkManager. Min SDK 26. Package: `com.iyidden.commander`. Dark mode default, iYidden brand (yellow + blue undertones).
- **Transport during dev:** plain HTTP/WS on localhost. Caddy + Let's Encrypt once domain is provisioned. Skip self-signed entirely.
- **FCM:** mock notifications until step 9.

## Anthropic API usage

Only on the backend. Used for:
- Rabbi-readable summaries for emergency mode (system prompt frames the reader as a rabbi who may not code).
- "What's new since I last checked" digests.
- One-liner activity descriptions per lane.

Use **Claude Sonnet** (`claude-sonnet-4-6`) for these. Always include prompt caching for the system prompt — the rabbi-summary system prompt is reused on every call.

## Don't

- Don't propose adding freeform Claude chat to the phone.
- Don't add git operations beyond the whitelisted set (log/diff read, merge to main if tests green, revert last commit, abort lane, switch to existing branch). No force-push, no rebase, no arbitrary commands.
- Don't broaden zal-mode override — calendar-verified days only, otherwise mashpia PIN.
- Don't store PINs in plaintext, ever. Argon2id, server-side, with the Android device storing only an envelope/derived secret for offline PIN entry during zal.

## Testing philosophy

Critical paths must not silently break: PIN hash/verify, zal mode activation/deactivation, calendar override gate, emergency mode actions, git safe-writes. Don't chase 100% coverage.
