"""Shared FastAPI dependencies."""

from __future__ import annotations

from typing import Annotated

import aiosqlite
from fastapi import Depends, Header, HTTPException, Request, status

from .auth import AuthError, decode_access_token
from .config import get_settings


async def get_db(request: Request) -> aiosqlite.Connection:
    db: aiosqlite.Connection | None = getattr(request.app.state, "db", None)
    if db is None:
        raise RuntimeError("db not initialized on app.state")
    return db


def require_device(
    authorization: Annotated[str | None, Header()] = None,
) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "missing bearer token")
    token = authorization.split(" ", 1)[1].strip()
    try:
        payload = decode_access_token(token)
    except AuthError as e:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, str(e)) from e
    device_id = payload.get("sub")
    if not device_id:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "no device in token")
    return device_id


def require_agent_api_key(
    authorization: Annotated[str | None, Header()] = None,
) -> None:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "missing bearer token")
    presented = authorization.split(" ", 1)[1].strip()
    expected = get_settings().agent_api_key
    # Length-safe compare
    import hmac
    if not hmac.compare_digest(presented, expected):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "bad agent key")


DBDep = Annotated[aiosqlite.Connection, Depends(get_db)]
DeviceDep = Annotated[str, Depends(require_device)]
