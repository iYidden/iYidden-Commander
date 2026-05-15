"""Phone WebSocket. Auth via ?token=<JWT> on the connect URL.

Step-1 behaviors:
- subscribe -> replay lane_snapshot, then stream lane_update/question/lane_removed
- answer_question -> resolve question, forward to agent if any
- git_op -> forward op to the agent owning the lane
- request_zal_override -> stubbed (calendar check is step 4/5)
- emergency_action -> stubbed
- request_freeform_unlock -> stubbed
- ping -> pong
"""

from __future__ import annotations

import asyncio
import json
import uuid

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect, status
from pydantic import TypeAdapter, ValidationError

from .. import __version__
from ..auth import AuthError, decode_access_token
from ..logging_setup import get_logger
from ..models import PhoneInbound
from ..state.agents import get_agent_registry
from ..state.lanes import get_lane_store

log = get_logger(__name__)
router = APIRouter()
_PHONE_IN = TypeAdapter(PhoneInbound)  # type: ignore[var-annotated]


async def _send(ws: WebSocket, obj: dict) -> None:
    await ws.send_text(json.dumps(obj, default=str))


@router.websocket("/ws/phone")
async def phone_ws(ws: WebSocket, token: str = Query(...)) -> None:
    try:
        payload = decode_access_token(token)
        device_id = payload["sub"]
    except (AuthError, KeyError):
        await ws.close(code=4010)
        return

    await ws.accept()
    store = get_lane_store()
    sub = store.subscribe()
    log.info("phone_ws_connected", device_id=device_id, server_version=__version__)

    pump_task = asyncio.create_task(_pump_to_phone(ws, sub))
    try:
        while True:
            raw = await ws.receive_text()
            try:
                msg = _PHONE_IN.validate_json(raw)
            except (json.JSONDecodeError, ValidationError) as e:
                await _send(ws, {"v": 0, "type": "error", "code": 4002, "message": str(e)})
                continue

            ref = getattr(msg, "id", None)
            t = msg.type

            if t == "subscribe":
                lanes = await store.snapshot()
                await _send(
                    ws,
                    {
                        "v": 0,
                        "type": "lane_snapshot",
                        "lanes": [lane.model_dump(mode="json") for lane in lanes],
                    },
                )
                if ref:
                    await _send(ws, {"v": 0, "type": "ack", "ref_id": ref})

            elif t == "answer_question":
                q = await store.resolve_question(msg.question_id, msg.choice_index)
                if q is None:
                    await _send(
                        ws,
                        {
                            "v": 0,
                            "type": "error",
                            "code": 4040,
                            "message": "no such question",
                            "ref_id": ref,
                        },
                    )
                    continue
                # Forward to any connected agent — in step 1 we broadcast.
                await get_agent_registry().broadcast(
                    {
                        "v": 0,
                        "type": "question_answered",
                        "question_id": msg.question_id,
                        "choice_index": msg.choice_index,
                    }
                )
                if ref:
                    await _send(ws, {"v": 0, "type": "ack", "ref_id": ref})

            elif t == "git_op":
                op_id = str(uuid.uuid4())
                await get_agent_registry().broadcast(
                    {
                        "v": 0,
                        "type": "git_op_request",
                        "op_id": op_id,
                        "lane_id": msg.lane_id,
                        "op": msg.op,
                        "args": msg.args,
                    }
                )
                if ref:
                    await _send(ws, {"v": 0, "type": "ack", "ref_id": ref})

            elif t == "request_zal_override":
                # Stubbed in step 1 — calendar check arrives with zal mode (step 4).
                await _send(
                    ws,
                    {
                        "v": 0,
                        "type": "zal_override_result",
                        "granted": False,
                        "reason": "calendar check not implemented yet",
                    },
                )

            elif t == "emergency_action":
                # Stubbed — full flow lands in step 8.
                await _send(
                    ws,
                    {
                        "v": 0,
                        "type": "ack",
                        "ref_id": ref,
                    },
                )

            elif t == "request_freeform_unlock":
                await _send(
                    ws,
                    {
                        "v": 0,
                        "type": "freeform_unlock_result",
                        "granted": False,
                        "reason": "freeform unlock not implemented yet",
                    },
                )

            elif t == "ping":
                await _send(ws, {"v": 0, "type": "pong"})

    except WebSocketDisconnect:
        log.info("phone_ws_disconnected", device_id=device_id)
    except Exception as e:
        log.exception("phone_ws_error", error=str(e))
        try:
            await ws.close(code=status.WS_1011_INTERNAL_ERROR)
        except RuntimeError:
            pass
    finally:
        pump_task.cancel()
        store.unsubscribe(sub)


async def _pump_to_phone(ws: WebSocket, sub) -> None:
    try:
        while True:
            msg = await sub.queue.get()
            msg = {"v": 0, **msg}
            await ws.send_text(json.dumps(msg, default=str))
    except asyncio.CancelledError:
        raise
    except WebSocketDisconnect:
        return
    except Exception as e:
        get_logger(__name__).exception("phone_pump_error", error=str(e))
