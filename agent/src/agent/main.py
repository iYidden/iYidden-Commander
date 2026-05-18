"""iYidden Commander agent — minimum viable version.

Connects to backend, authenticates, registers, sends heartbeats, logs incoming messages.
"""
import asyncio
import json
import logging
import socket
import sys

import structlog
import websockets
from websockets.exceptions import ConnectionClosed

from agent.config import get_settings

AGENT_VERSION = "0.1.0"
LANE_CAPACITY = 4


def setup_logging(level: str) -> None:
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=level.upper(),
    )
    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.add_log_level,
            structlog.dev.ConsoleRenderer(),
        ]
    )


log = structlog.get_logger()


async def receive_loop(ws) -> None:
    """Receive and log any messages from the backend."""
    async for raw in ws:
        try:
            msg = json.loads(raw)
            log.info("received", msg=msg)
        except json.JSONDecodeError:
            log.warning("non_json_received", raw=raw)


async def heartbeat_loop(ws, interval: int) -> None:
    """Send a heartbeat every `interval` seconds until the socket dies."""
    while True:
        await asyncio.sleep(interval)
        await ws.send(json.dumps({"v": 0, "type": "heartbeat"}))
        log.debug("heartbeat_sent")


async def connect_once(settings, state: dict) -> None:
    """One connection attempt. Sets state['registered']=True on successful register."""
    headers = {"Authorization": f"Bearer {settings.agent_api_key}"}
    log.info("connecting", url=settings.backend_url, agent=settings.agent_name)
    async with websockets.connect(settings.backend_url, additional_headers=headers) as ws:
        log.info("connected")

        register = {
            "v": 0,
            "type": "register",
            "agent_id": settings.agent_name,
            "hostname": socket.gethostname(),
            "lane_capacity": LANE_CAPACITY,
            "agent_version": AGENT_VERSION,
        }
        await ws.send(json.dumps(register))
        log.info("registered", agent_id=settings.agent_name, hostname=register["hostname"])
        state["registered"] = True

        await asyncio.gather(receive_loop(ws), heartbeat_loop(ws, settings.heartbeat_interval))


async def run() -> None:
    settings = get_settings()
    setup_logging(settings.log_level)
    log.info("agent_starting", name=settings.agent_name)
    backoff = 1
    while True:
        state = {"registered": False}
        try:
            await connect_once(settings, state)
        except ConnectionClosed as e:
            log.warning("connection_closed", code=e.code, reason=e.reason)
        except Exception as e:
            log.error("connection_error", error=str(e), type=type(e).__name__)
        if state["registered"]:
            backoff = 1
        log.info("reconnecting_in", seconds=backoff, reset=state["registered"])
        await asyncio.sleep(backoff)
        backoff = min(backoff * 2, 60)


def main() -> None:
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        log.info("agent_stopped")


if __name__ == "__main__":
    main()
