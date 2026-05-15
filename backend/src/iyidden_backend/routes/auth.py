"""Device-side auth: register a phone with a one-time token, refresh access JWTs."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from ..auth import (
    consume_device_registration_token,
    create_access_token,
    create_refresh_token,
    rotate_refresh_token,
    sha256_hex,
)
from ..deps import DBDep

router = APIRouter(prefix="/auth", tags=["auth"])


class DeviceRegisterIn(BaseModel):
    registration_token: str
    label: str = Field(min_length=1, max_length=64)


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    device_id: str


@router.post("/device/register", response_model=TokenPair)
async def register_device(body: DeviceRegisterIn, db: DBDep) -> TokenPair:
    label_hint = await consume_device_registration_token(db, body.registration_token)
    if label_hint is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid or used registration token")

    device_id = str(uuid.uuid4())
    await db.execute(
        "INSERT INTO devices (id, label, registration_token_hash, created_at) VALUES (?, ?, ?, ?)",
        (
            device_id,
            body.label or label_hint or "phone",
            sha256_hex(body.registration_token),
            datetime.now(UTC).isoformat(),
        ),
    )
    await db.commit()

    _, refresh = await create_refresh_token(db, device_id)
    access = create_access_token(device_id)
    return TokenPair(access_token=access, refresh_token=refresh, device_id=device_id)


class RefreshIn(BaseModel):
    refresh_token: str


@router.post("/refresh", response_model=TokenPair)
async def refresh(body: RefreshIn, db: DBDep) -> TokenPair:
    result = await rotate_refresh_token(db, body.refresh_token)
    if result is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid refresh token")
    device_id, _new_id, new_refresh = result
    access = create_access_token(device_id)
    return TokenPair(access_token=access, refresh_token=new_refresh, device_id=device_id)
