# iYidden Commander — original build spec

This is the build specification the project was scoped from. Treat it as canonical for product intent. Implementation decisions deviating from it should be documented in the relevant component's README, not silently.

---

## Purpose

The user is a yeshiva bochur learning 7am–9:30pm. He runs multiple Claude Code agents in parallel on iYidden Kosher Filter, the flagship product of his company iYidden. He needs:

1. A way to supervise those agents from his phone with minimal time spent. Every interaction during seder is bittul Torah.
2. A "zal mode" that locks his Android phone down to only iYidden Commander during seder, controlled by a PIN held by his mashpia.

This is **not** a general Claude Code client. Freeform interaction with Claude is intentionally prevented from the phone — that's the whole point.

## System architecture

Three components: VPS backend, dev-machine agent, Android app. See [`README.md`](../README.md) and [`CLAUDE.md`](../CLAUDE.md).

## Build order

1. VPS backend skeleton
2. Dev-machine agent skeleton (fake lane data)
3. Android app skeleton
4. Zal mode (Device Owner, PIN, schedule, lock task)
5. Real lane monitoring (tmux, git watcher, idle detection)
6. Git GUI overlay (safe-write ops only)
7. Question/answer flow (MCP `ask_supervisor`)
8. Emergency mode (Anthropic-API summaries)
9. FCM notifications
10. Polish, debug-build PIN exposure, production hardening

## Confirmed decisions (resolved during scoping)

- **VPS:** none yet, provision before step 3. Plain HTTP locally until then. Once a domain is available, Caddy + Let's Encrypt; skipping self-signed certs.
- **Dev machine:** Windows laptop. Agent runs in WSL2 Ubuntu.
- **Android theme:** dark mode default; iYidden brand colors — yellow + blue undertones.
- **FCM:** mock until step 9.
- **Package name:** `com.iyidden.commander`.
- **Mashpia PIN setup:** single-use 24h token → URL shared with mashpia out-of-band → mashpia sets PIN + 12-char backup password.
- **Max-freeform-minutes for emergency unlock:** set by the mashpia (no app default).
- **Terminal log during emergency-mode unlock:** kept locally, NOT shipped to mashpia.
- **Zal-mode override:** user can override if backend verifies via Hebcal + hardcoded Chabad-dates table that today is Friday / non–Yom-Tov secular holiday / Chabad holiday. No PIN needed when calendar approves.

## Hard product rules

1. No freeform Claude input from the phone except the time-gated emergency mode unlock.
2. Every phone screen answerable in under 60 seconds.
3. Async-first design — user checks in at lunch and after seder.
4. Phone git operations limited to: view log, view diff, merge to main (if tests green), revert last commit, abort lane, switch to existing branch. Nothing else.
