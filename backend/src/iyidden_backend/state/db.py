"""SQLite persistence. Stores only durable state: devices, refresh tokens,
mashpia config, mashpia setup tokens, emergency-event audit log.

Live lane data lives in-process (see state.lanes) since it's volatile and
sourced from the agent on every reconnect.
"""

from __future__ import annotations

from pathlib import Path

import aiosqlite

SCHEMA = """
CREATE TABLE IF NOT EXISTS devices (
    id              TEXT PRIMARY KEY,
    label           TEXT NOT NULL,
    registration_token_hash TEXT NOT NULL,
    created_at      TEXT NOT NULL,
    revoked_at      TEXT
);

CREATE TABLE IF NOT EXISTS refresh_tokens (
    token_id        TEXT PRIMARY KEY,
    device_id       TEXT NOT NULL REFERENCES devices(id),
    token_hash      TEXT NOT NULL,
    issued_at       TEXT NOT NULL,
    expires_at      TEXT NOT NULL,
    revoked_at      TEXT,
    replaced_by     TEXT
);

CREATE TABLE IF NOT EXISTS mashpia_config (
    id              INTEGER PRIMARY KEY CHECK (id = 1),
    pin_hash        TEXT NOT NULL,
    backup_pw_hash  TEXT NOT NULL,
    max_freeform_minutes INTEGER NOT NULL DEFAULT 10,
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS mashpia_setup_tokens (
    token_hash      TEXT PRIMARY KEY,
    issued_at       TEXT NOT NULL,
    expires_at      TEXT NOT NULL,
    used_at         TEXT,
    purpose         TEXT NOT NULL DEFAULT 'initial_pin'
);

CREATE TABLE IF NOT EXISTS device_registration_tokens (
    token_hash      TEXT PRIMARY KEY,
    issued_at       TEXT NOT NULL,
    expires_at      TEXT NOT NULL,
    used_at          TEXT,
    label_hint      TEXT
);

CREATE TABLE IF NOT EXISTS emergency_events (
    id              TEXT PRIMARY KEY,
    lane_id         TEXT,
    kind            TEXT NOT NULL,
    summary_md      TEXT,
    action_taken    TEXT,
    approved_by_hash_prefix TEXT,
    created_at      TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_refresh_device ON refresh_tokens(device_id);
CREATE INDEX IF NOT EXISTS idx_emergency_created ON emergency_events(created_at);
"""


async def open_db(db_path: Path) -> aiosqlite.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = await aiosqlite.connect(str(db_path))
    conn.row_factory = aiosqlite.Row
    await conn.execute("PRAGMA journal_mode=WAL;")
    await conn.execute("PRAGMA foreign_keys=ON;")
    await conn.executescript(SCHEMA)
    await conn.commit()
    return conn
