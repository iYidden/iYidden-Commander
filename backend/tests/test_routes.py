"""End-to-end HTTP route tests via httpx ASGI transport."""

from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_health(client):
    r = await client.get("/health")
    assert r.status_code == 200
    assert r.json()["ok"] is True


@pytest.mark.asyncio
async def test_lanes_requires_auth(client):
    r = await client.get("/lanes")
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_full_device_registration_and_lanes(client, app):
    from iyidden_backend.auth import create_device_registration_token

    token = await create_device_registration_token(app.state.db, label_hint="phone-1")

    r = await client.post(
        "/auth/device/register",
        json={"registration_token": token, "label": "leo's phone"},
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["device_id"]
    assert data["access_token"]
    assert data["refresh_token"]

    r2 = await client.get("/lanes", headers={"Authorization": f"Bearer {data['access_token']}"})
    assert r2.status_code == 200
    assert r2.json() == []


@pytest.mark.asyncio
async def test_registration_token_cannot_be_reused(client, app):
    from iyidden_backend.auth import create_device_registration_token

    token = await create_device_registration_token(app.state.db)
    r1 = await client.post("/auth/device/register", json={"registration_token": token, "label": "a"})
    assert r1.status_code == 200
    r2 = await client.post("/auth/device/register", json={"registration_token": token, "label": "b"})
    assert r2.status_code == 401


@pytest.mark.asyncio
async def test_mashpia_setup_happy_path(client, app):
    from iyidden_backend.auth import create_mashpia_setup_token

    token = await create_mashpia_setup_token(app.state.db)
    r = await client.get(f"/mashpia/setup/{token}")
    assert r.status_code == 200
    assert "Set the supervisor PIN" in r.text

    r = await client.post(
        f"/mashpia/setup/{token}",
        data={
            "pin": "123456",
            "pin_confirm": "123456",
            "backup_pw": "correct horse battery staple",
            "backup_pw_confirm": "correct horse battery staple",
            "max_freeform_minutes": "15",
        },
    )
    assert r.status_code == 200
    assert "Done" in r.text

    r = await client.get("/mashpia/status")
    assert r.status_code == 200
    body = r.json()
    assert body["configured"] is True
    assert body["max_freeform_minutes"] == 15


@pytest.mark.asyncio
async def test_mashpia_setup_token_burns(client, app):
    from iyidden_backend.auth import create_mashpia_setup_token

    token = await create_mashpia_setup_token(app.state.db)
    body = {
        "pin": "123456",
        "pin_confirm": "123456",
        "backup_pw": "correct horse battery staple",
        "backup_pw_confirm": "correct horse battery staple",
        "max_freeform_minutes": "10",
    }
    r = await client.post(f"/mashpia/setup/{token}", data=body)
    assert r.status_code == 200
    # Second use must fail
    r = await client.post(f"/mashpia/setup/{token}", data=body)
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_mashpia_setup_mismatched_pin(client, app):
    from iyidden_backend.auth import create_mashpia_setup_token

    token = await create_mashpia_setup_token(app.state.db)
    r = await client.post(
        f"/mashpia/setup/{token}",
        data={
            "pin": "111111",
            "pin_confirm": "222222",
            "backup_pw": "correct horse battery staple",
            "backup_pw_confirm": "correct horse battery staple",
            "max_freeform_minutes": "10",
        },
    )
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_mashpia_setup_short_backup_pw(client, app):
    from iyidden_backend.auth import create_mashpia_setup_token

    token = await create_mashpia_setup_token(app.state.db)
    r = await client.post(
        f"/mashpia/setup/{token}",
        data={
            "pin": "123456",
            "pin_confirm": "123456",
            "backup_pw": "short",
            "backup_pw_confirm": "short",
            "max_freeform_minutes": "10",
        },
    )
    # FastAPI's Form() with no explicit minlength returns 422 for the validator
    # check; our handler returns 400. Either is fine — we just must not 200.
    assert r.status_code in (400, 422)
