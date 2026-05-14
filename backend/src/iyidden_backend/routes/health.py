from fastapi import APIRouter

from ..state.agents import get_agent_registry
from ..state.lanes import get_lane_store

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict:
    return {
        "ok": True,
        "lanes": len(await get_lane_store().snapshot()),
        "agents": get_agent_registry().count,
        "subscribers": get_lane_store().subscriber_count,
    }
