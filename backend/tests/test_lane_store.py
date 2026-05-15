"""LaneStore pub/sub correctness."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

import pytest

from iyidden_backend.models import Lane, Question
from iyidden_backend.state.lanes import get_lane_store


def _make_lane(id_: str = "lane-1") -> Lane:
    return Lane(
        id=id_,
        agent_id="agent-1",
        branch="feat/x",
        worktree_path="/tmp/x",
        updated_at=datetime.now(UTC),
    )


@pytest.mark.asyncio
async def test_upsert_fan_out():
    store = get_lane_store()
    sub = store.subscribe()
    try:
        await store.upsert_lane(_make_lane())
        msg = await asyncio.wait_for(sub.queue.get(), timeout=1.0)
        assert msg["type"] == "lane_update"
        assert msg["lane"]["id"] == "lane-1"
    finally:
        store.unsubscribe(sub)


@pytest.mark.asyncio
async def test_remove_fan_out():
    store = get_lane_store()
    await store.upsert_lane(_make_lane())
    sub = store.subscribe()
    try:
        await store.remove_lane("lane-1")
        msg = await asyncio.wait_for(sub.queue.get(), timeout=1.0)
        assert msg["type"] == "lane_removed"
    finally:
        store.unsubscribe(sub)


@pytest.mark.asyncio
async def test_question_updates_lane_pending():
    store = get_lane_store()
    await store.upsert_lane(_make_lane())
    sub = store.subscribe()
    try:
        q = Question(
            id="q1",
            lane_id="lane-1",
            prompt="Pick one",
            options=["a", "b"],
            created_at=datetime.now(UTC),
        )
        await store.add_question(q)
        m1 = await asyncio.wait_for(sub.queue.get(), timeout=1.0)
        assert m1["type"] == "question"
        # Lane is now flagged as pending — verify via snapshot
        lanes = await store.snapshot()
        assert lanes[0].pending_question_id == "q1"

        await store.resolve_question("q1", 0)
        m2 = await asyncio.wait_for(sub.queue.get(), timeout=1.0)
        assert m2["type"] == "question_resolved"
        lanes = await store.snapshot()
        assert lanes[0].pending_question_id is None
    finally:
        store.unsubscribe(sub)


@pytest.mark.asyncio
async def test_slow_subscriber_drops_not_blocks():
    store = get_lane_store()
    sub = store.subscribe()
    try:
        # Push more than the queue's maxsize without consuming.
        for i in range(200):
            lane = _make_lane(f"lane-{i}")
            await store.upsert_lane(lane)
        # Should not have hung. Queue size capped.
        assert sub.queue.qsize() <= 64
    finally:
        store.unsubscribe(sub)
