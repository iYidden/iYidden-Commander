"""Critical-path auth tests: PIN hashing, JWT lifecycle, refresh rotation,
mashpia-token single-use, device-token single-use."""

from __future__ import annotations

import pytest

from iyidden_backend.auth import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
    create_mashpia_setup_token,
    consume_mashpia_setup_token,
    create_device_registration_token,
    consume_device_registration_token,
    create_refresh_token,
    rotate_refresh_token,
    AuthError,
)


def test_password_roundtrip():
    h = hash_password("123456")
    assert verify_password(h, "123456")
    assert not verify_password(h, "123457")


def test_password_hashes_differ():
    a = hash_password("hello")
    b = hash_password("hello")
    assert a != b  # Argon2 includes a salt
    assert verify_password(a, "hello")
    assert verify_password(b, "hello")


def test_jwt_roundtrip():
    tok = create_access_token("device-xyz")
    payload = decode_access_token(tok)
    assert payload["sub"] == "device-xyz"
    assert payload["typ"] == "access"


def test_jwt_bad_secret_rejected():
    tok = create_access_token("device-xyz")
    # tamper the last char
    bad = tok[:-1] + ("a" if tok[-1] != "a" else "b")
    with pytest.raises(AuthError):
        decode_access_token(bad)


@pytest.mark.asyncio
async def test_mashpia_setup_token_single_use(app):
    db = app.state.db
    token = await create_mashpia_setup_token(db)
    assert await consume_mashpia_setup_token(db, token) is True
    assert await consume_mashpia_setup_token(db, token) is False


@pytest.mark.asyncio
async def test_mashpia_setup_token_unknown_rejected(app):
    db = app.state.db
    assert await consume_mashpia_setup_token(db, "nope") is False


@pytest.mark.asyncio
async def test_device_token_single_use(app):
    db = app.state.db
    token = await create_device_registration_token(db, label_hint="primary")
    label = await consume_device_registration_token(db, token)
    assert label == "primary"
    assert await consume_device_registration_token(db, token) is None


@pytest.mark.asyncio
async def test_refresh_rotation_invalidates_prior(app):
    db = app.state.db
    # Need an actual device row to satisfy the FK
    import uuid
    from datetime import datetime, timezone

    device_id = str(uuid.uuid4())
    await db.execute(
        "INSERT INTO devices (id, label, registration_token_hash, created_at) VALUES (?, ?, ?, ?)",
        (device_id, "test", "hash", datetime.now(timezone.utc).isoformat()),
    )
    await db.commit()

    _, refresh1 = await create_refresh_token(db, device_id)
    out = await rotate_refresh_token(db, refresh1)
    assert out is not None
    _, _, refresh2 = out
    # New token works once
    out2 = await rotate_refresh_token(db, refresh2)
    assert out2 is not None
    _, _, refresh3 = out2

    # Replay of the original token must fail AND nuke the chain (compromise signal).
    assert await rotate_refresh_token(db, refresh1) is None
    # Because of the reuse-nuke, even refresh3 is now revoked.
    assert await rotate_refresh_token(db, refresh3) is None
