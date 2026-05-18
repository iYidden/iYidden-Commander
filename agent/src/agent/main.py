"""iYidden Commander agent — minimum viable version.

Connects to backend, authenticates, logs welcome message, idles.
"""

import asyncio
import json
import logging
import sys

import structlog
import websockets
from websockets.exceptions import ConnectionClosed

from agent.config import get_settings


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


async def connect_once(settings) -> None:
    """One connection attempt."""
    headers = {"Authorization": f"Bearer {settings.agent_api_key}"}
    log.info("connecting", url=settings.backend_url, agent=settings.agent_name)

    async with websockets.connect(settings.backend_url, additional_headers=headers) as ws:
        log.info("connected")
        await receive_loop(ws)


async def run() -> None:
    settings = get_settings()
    setup_logging(settings.log_level)

    log.info("agent_starting", name=settings.agent_name)

    backoff = 1
    while True:
        try:
            await connect_once(settings)
            backoff = 1
        except ConnectionClosed as e:
            log.warning("connection_closed", code=e.code, reason=e.reason)
        except Exception as e:
            log.error("connection_error", error=str(e), type=type(e).__name__)

        log.info("reconnecting_in", seconds=backoff)
        await asyncio.sleep(backoff)
        backoff = min(backoff * 2, 60)


def main() -> None:
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        log.info("agent_stopped")


if __name__ == "__main__":
    main()
