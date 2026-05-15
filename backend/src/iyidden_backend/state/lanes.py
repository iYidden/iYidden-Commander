"""In-process lane store and pub/sub fan-out.

Lane state is volatile and resourced from the dev-machine agent on every
reconnect, so it lives in memory only. Subscribers are async-iterable queues
held by each phone websocket.

Step-1 simplifications:
- Single backend process, no Redis. Move to Redis pub/sub when we scale beyond
  one process (not needed for one user).
- Subscriber drops on slow consumers (bounded queue, full = drop oldest).
"""

from __future__ import annotations

import asyncio
from collections import deque
from dataclasses import dataclass, field
from typing import Any

from ..logging_setup import get_logger
from ..models import Lane, Question

log = get_logger(__name__)


@dataclass(eq=False)
class _Subscriber:
    queue: asyncio.Queue[dict[str, Any]] = field(default_factory=lambda: asyncio.Queue(maxsize=64))

    async def push(self, msg: dict[str, Any]) -> None:
        try:
            self.queue.put_nowait(msg)
        except asyncio.QueueFull:
            try:
                self.queue.get_nowait()
            except asyncio.QueueEmpty:
                pass
            try:
                self.queue.put_nowait(msg)
            except asyncio.QueueFull:
                log.warning("subscriber_queue_drop", reason="full_after_evict")


class LaneStore:
    def __init__(self) -> None:
        self._lanes: dict[str, Lane] = {}
        self._questions: dict[str, Question] = {}
        self._subscribers: set[_Subscriber] = set()
        self._recent: deque[dict[str, Any]] = deque(maxlen=128)
        self._lock = asyncio.Lock()

    # ---- mutation ---------------------------------------------------------

    async def upsert_lane(self, lane: Lane) -> None:
        async with self._lock:
            self._lanes[lane.id] = lane
        await self._broadcast({"type": "lane_update", "lane": lane.model_dump(mode="json")})

    async def remove_lane(self, lane_id: str) -> None:
        async with self._lock:
            self._lanes.pop(lane_id, None)
        await self._broadcast({"type": "lane_removed", "lane_id": lane_id})

    async def add_question(self, q: Question) -> None:
        async with self._lock:
            self._questions[q.id] = q
            lane = self._lanes.get(q.lane_id)
            if lane is not None:
                lane = lane.model_copy(update={"pending_question_id": q.id})
                self._lanes[q.lane_id] = lane
        await self._broadcast({"type": "question", "question": q.model_dump(mode="json")})

    async def resolve_question(
        self, question_id: str, choice_index: int | None = None
    ) -> Question | None:
        async with self._lock:
            q = self._questions.get(question_id)
            if q is None:
                return None
            updated = q.model_copy(
                update={
                    "answered_choice_index": choice_index,
                    "answered_at": q.created_at if choice_index is None else None,
                }
            )
            self._questions[question_id] = updated
            lane = self._lanes.get(q.lane_id)
            if lane and lane.pending_question_id == question_id:
                self._lanes[q.lane_id] = lane.model_copy(update={"pending_question_id": None})
        await self._broadcast({"type": "question_resolved", "question_id": question_id})
        return updated

    async def notify(
        self, title: str, body: str, severity: str = "info", lane_id: str | None = None
    ) -> None:
        await self._broadcast(
            {
                "type": "notification",
                "title": title,
                "body": body,
                "severity": severity,
                "lane_id": lane_id,
            }
        )

    # ---- read ------------------------------------------------------------

    async def snapshot(self) -> list[Lane]:
        async with self._lock:
            return list(self._lanes.values())

    async def get_question(self, qid: str) -> Question | None:
        async with self._lock:
            return self._questions.get(qid)

    # ---- pub/sub ---------------------------------------------------------

    def subscribe(self) -> _Subscriber:
        sub = _Subscriber()
        self._subscribers.add(sub)
        return sub

    def unsubscribe(self, sub: _Subscriber) -> None:
        self._subscribers.discard(sub)

    async def _broadcast(self, msg: dict[str, Any]) -> None:
        self._recent.append(msg)
        dead: list[_Subscriber] = []
        for sub in self._subscribers:
            try:
                await sub.push(msg)
            except Exception:
                dead.append(sub)
        for d in dead:
            self._subscribers.discard(d)

    # ---- diagnostic ------------------------------------------------------

    @property
    def subscriber_count(self) -> int:
        return len(self._subscribers)


_singleton: LaneStore | None = None


def get_lane_store() -> LaneStore:
    global _singleton
    if _singleton is None:
        _singleton = LaneStore()
    return _singleton


def reset_lane_store_for_tests() -> None:
    global _singleton
    _singleton = None
