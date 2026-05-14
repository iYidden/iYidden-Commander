"""Dev-machine agent WebSocket. Auth via the AGENT_API_KEY env var, presented
as a `Bearer` token in the Authorization header on the upgrade request.

Agents push lane_state / question_ask updates; the server responds with
question_answered / git_op_request / emergency_command / start_freeform_session.
"""

from __future__ import annotations

import asyncio
import hmac
import json
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Header, WebSocket, WebSocketDisconnect, status
from pydantic import TypeAdapter, ValidationError

from .. import __version__
from ..config import get_settings
from ..logging_setup import get_logger
from ..models import AgentInbound, Question
from ..state.agents import AgentConnection, get_agent_registry
from ..state.lanes import get_lane_store

log = get_logger(__name__)
router = APIRouter()
_AGENT_IN = TypeAdapter(AgentInbound)


@router.websocket("/ws/agent")
async def agent_ws(ws: WebSocket, authorization: str | None = Header(default=None)) -> None:
    expected = get_settings().agent_api_key
    presented = ""
    if authorization and authorization.lower().startswith("bearer "):
        presented = authorization.split(" ", 1)[1].strip()
    if not presented or not hmac.compare_digest(presented, expected):
        await ws.close(code=4010)
        return

    await ws.accept()
    registry = get_agent_registry()
    store = get_lane_store()

    agent_id: str | None = None
    send_lock = asyncio.Lock()

    async def send(obj: dict) -> None:
        async with send_lock:
            await ws.send_text(json.dumps(obj, default=str))

    await send({"v": 0, "type": "welcome", "server_version": __version__, "max_lanes": 8})

    try:
        while True:
            raw = await ws.receive_text()
            try:
                msg = _AGENT_IN.validate_json(raw)
            except (json.JSONDecodeError, ValidationError) as e:
                await send({"v": 0, "type": "error", "code": 4002, "message": str(e)})
                continue

            t = msg.type
            if t == "register":
                agent_id = msg.agent_id
                await registry.register(
                    AgentConnection(agent_id=agent_id, hostname=msg.hostname, send=send)
                )
                log.info(
                    "agent_registered",
                    agent_id=agent_id,
                    hostname=msg.hostname,
                    agent_version=msg.agent_version,
                )

            elif t == "lane_state":
                await store.upsert_lane(msg.lane)

            elif t == "lane_removed":
                await store.remove_lane(msg.lane_id)

            elif t == "question_ask":
                q = Question(
                    id=str(uuid.uuid4()),
                    lane_id=msg.lane_id,
                    prompt=msg.prompt,
                    options=msg.options,
                    created_at=datetime.now(timezone.utc),
                )
                await store.add_question(q)

            elif t == "git_op_result":
                # Step 1: log and forward to phone subscribers via the same
                # lane-update channel (cheap notification mechanism).
                log.info(
                    "git_op_result",
                    op_id=msg.op_id,
                    ok=msg.ok,
                    error=msg.error,
                )
                await store.notify(
                    title="Git op finished" if msg.ok else "Git op failed",
                    body=(msg.output or "")[:200] if msg.ok else (msg.error or "")[:200],
                    severity="info" if msg.ok else "error",
                )

            elif t == "freeform_session_event":
                log.info(
                    "freeform_event",
                    session_id=msg.session_id,
                    kind=msg.kind,
                )

            elif t == "heartbeat":
                pass  # presence is implicit in the WS staying open

    except WebSocketDisconnect:
        log.info("agent_ws_disconnected", agent_id=agent_id)
    except Exception as e:
        log.exception("agent_ws_error", error=str(e))
        try:
            await ws.close(code=status.WS_1011_INTERNAL_ERROR)
        except RuntimeError:
            pass
    finally:
        if agent_id is not None:
            await registry.unregister(agent_id)
