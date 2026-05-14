"""Registry of currently-connected dev-machine agents. Used by the server
to address a specific agent when forwarding phone commands."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any


@dataclass
class AgentConnection:
    agent_id: str
    hostname: str
    send: callable  # type: ignore[valid-type]  # async (dict) -> None


class AgentRegistry:
    def __init__(self) -> None:
        self._agents: dict[str, AgentConnection] = {}
        self._lock = asyncio.Lock()

    async def register(self, conn: AgentConnection) -> None:
        async with self._lock:
            self._agents[conn.agent_id] = conn

    async def unregister(self, agent_id: str) -> None:
        async with self._lock:
            self._agents.pop(agent_id, None)

    async def get(self, agent_id: str) -> AgentConnection | None:
        async with self._lock:
            return self._agents.get(agent_id)

    async def broadcast(self, msg: dict[str, Any]) -> None:
        async with self._lock:
            agents = list(self._agents.values())
        for a in agents:
            try:
                await a.send(msg)
            except Exception:
                pass

    @property
    def count(self) -> int:
        return len(self._agents)


_singleton: AgentRegistry | None = None


def get_agent_registry() -> AgentRegistry:
    global _singleton
    if _singleton is None:
        _singleton = AgentRegistry()
    return _singleton


def reset_agent_registry_for_tests() -> None:
    global _singleton
    _singleton = None
