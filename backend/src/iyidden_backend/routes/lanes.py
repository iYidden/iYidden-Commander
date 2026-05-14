"""Read-only lane endpoints. Step 1 keeps these for diagnostics; the phone
receives lane state over the websocket. Git ops are forwarded over WS too
(see ws.phone). These HTTP endpoints exist for human/curl introspection."""

from __future__ import annotations

from fastapi import APIRouter

from ..deps import DeviceDep
from ..models import Lane
from ..state.lanes import get_lane_store

router = APIRouter(prefix="/lanes", tags=["lanes"])


@router.get("", response_model=list[Lane])
async def list_lanes(_device: DeviceDep) -> list[Lane]:
    store = get_lane_store()
    return await store.snapshot()
