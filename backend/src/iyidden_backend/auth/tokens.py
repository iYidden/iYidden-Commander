"""One-shot tokens that don't fit the JWT model:

- Mashpia setup tokens: single-use, 24h, gates the PIN-set page
- Device registration tokens: single-use, gates first /auth/device/register
- Refresh tokens: long-lived, rotating, server-side hashed
"""

from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta

import aiosqlite

from ..config import get_settings


def new_random_token(num_bytes: int = 32) -> str:
    return secrets.token_urlsafe(num_bytes)


def sha256_hex(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _now() -> datetime:
    return datetime.now(UTC)


# ---- Mashpia setup tokens -------------------------------------------------


async def create_mashpia_setup_token(db: aiosqlite.Connection) -> str:
    settings = get_settings()
    token = new_random_token()
    issued = _now()
    expires = issued + timedelta(seconds=settings.mashpia_setup_token_ttl_seconds)
    await db.execute(
        "INSERT INTO mashpia_setup_tokens (token_hash, issued_at, expires_at, purpose) "
        "VALUES (?, ?, ?, 'initial_pin')",
        (sha256_hex(token), issued.isoformat(), expires.isoformat()),
    )
    await db.commit()
    return token


async def consume_mashpia_setup_token(db: aiosqlite.Connection, token: str) -> bool:
    h = sha256_hex(token)
    now = _now()
    cur = await db.execute(
        "SELECT expires_at, used_at FROM mashpia_setup_tokens WHERE token_hash = ?",
        (h,),
    )
    row = await cur.fetchone()
    if not row:
        return False
    if row["used_at"] is not None:
        return False
    if datetime.fromisoformat(row["expires_at"]) < now:
        return False
    await db.execute(
        "UPDATE mashpia_setup_tokens SET used_at = ? WHERE token_hash = ?",
        (now.isoformat(), h),
    )
    await db.commit()
    return True


# ---- Device registration tokens -------------------------------------------


async def create_device_registration_token(
    db: aiosqlite.Connection, label_hint: str = "", ttl_seconds: int = 3600
) -> str:
    token = new_random_token()
    issued = _now()
    expires = issued + timedelta(seconds=ttl_seconds)
    await db.execute(
        "INSERT INTO device_registration_tokens (token_hash, issued_at, expires_at, label_hint) "
        "VALUES (?, ?, ?, ?)",
        (sha256_hex(token), issued.isoformat(), expires.isoformat(), label_hint),
    )
    await db.commit()
    return token


async def consume_device_registration_token(db: aiosqlite.Connection, token: str) -> str | None:
    """Returns label_hint if valid+unused+unexpired, else None. Marks used."""
    h = sha256_hex(token)
    now = _now()
    cur = await db.execute(
        "SELECT expires_at, used_at, label_hint FROM device_registration_tokens "
        "WHERE token_hash = ?",
        (h,),
    )
    row = await cur.fetchone()
    if not row:
        return None
    if row["used_at"] is not None:
        return None
    if datetime.fromisoformat(row["expires_at"]) < now:
        return None
    await db.execute(
        "UPDATE device_registration_tokens SET used_at = ? WHERE token_hash = ?",
        (now.isoformat(), h),
    )
    await db.commit()
    return row["label_hint"] or ""


# ---- Refresh tokens -------------------------------------------------------


async def create_refresh_token(db: aiosqlite.Connection, device_id: str) -> tuple[str, str]:
    """Returns (token_id, plaintext_token). Plaintext is returned only here."""
    settings = get_settings()
    token_id = str(uuid.uuid4())
    plaintext = new_random_token(48)
    issued = _now()
    expires = issued + timedelta(seconds=settings.refresh_token_ttl_seconds)
    await db.execute(
        "INSERT INTO refresh_tokens (token_id, device_id, token_hash, issued_at, expires_at) "
        "VALUES (?, ?, ?, ?, ?)",
        (token_id, device_id, sha256_hex(plaintext), issued.isoformat(), expires.isoformat()),
    )
    await db.commit()
    return token_id, f"{token_id}.{plaintext}"


async def rotate_refresh_token(
    db: aiosqlite.Connection, presented: str
) -> tuple[str, str, str] | None:
    """Validate the presented refresh token, mark it replaced, mint a new one.
    Returns (device_id, new_token_id, new_token_plaintext) on success."""
    parts = presented.split(".", 1)
    if len(parts) != 2:
        return None
    token_id, plaintext = parts
    now = _now()
    cur = await db.execute(
        "SELECT device_id, token_hash, expires_at, revoked_at, replaced_by "
        "FROM refresh_tokens WHERE token_id = ?",
        (token_id,),
    )
    row = await cur.fetchone()
    if not row:
        return None
    if row["revoked_at"] is not None or row["replaced_by"] is not None:
        # Reuse of a rotated token: nuke the whole chain for this device.
        await db.execute(
            "UPDATE refresh_tokens SET revoked_at = ? WHERE device_id = ? AND revoked_at IS NULL",
            (now.isoformat(), row["device_id"]),
        )
        await db.commit()
        return None
    if datetime.fromisoformat(row["expires_at"]) < now:
        return None
    if row["token_hash"] != sha256_hex(plaintext):
        return None

    new_id, new_token = await create_refresh_token(db, row["device_id"])
    await db.execute(
        "UPDATE refresh_tokens SET replaced_by = ?, revoked_at = ? WHERE token_id = ?",
        (new_id, now.isoformat(), token_id),
    )
    await db.commit()
    return row["device_id"], new_id, new_token


async def revoke_refresh_token(db: aiosqlite.Connection, token_id: str) -> None:
    await db.execute(
        "UPDATE refresh_tokens SET revoked_at = ? WHERE token_id = ? AND revoked_at IS NULL",
        (_now().isoformat(), token_id),
    )
    await db.commit()
