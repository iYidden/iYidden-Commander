"""LLM client interface. Step 1 ships a deterministic stub so the rest of
the system can be exercised without burning credits.

Real Anthropic calls are wired in step 8. When that lands:
- Use ``claude-sonnet-4-6``.
- Always include a cached system prompt (the rabbi-summary one is reused
  on every emergency call, so caching is high-value).
"""

from __future__ import annotations

from typing import Protocol


class LLMClient(Protocol):
    async def rabbi_summary(self, lane_state: dict, recent_events: list[dict]) -> str: ...
    async def whats_new_digest(self, commits: list[dict], diff_text: str) -> str: ...
    async def lane_activity_oneliner(self, last_lines: str) -> str: ...


class StubLLMClient:
    async def rabbi_summary(self, lane_state: dict, recent_events: list[dict]) -> str:
        branch = lane_state.get("branch", "unknown branch")
        return (
            f"The agent working on **{branch}** has paused. "
            "The technical question it raised cannot be answered without the bochur. "
            "Options below let you stop, pause, allow him a limited unlock, or do nothing."
        )

    async def whats_new_digest(self, commits: list[dict], diff_text: str) -> str:
        if not commits:
            return "Nothing new since last check."
        msgs = "\n".join(f"- {c.get('message', '(no msg)')}" for c in commits[:5])
        return f"Recent commits:\n{msgs}"

    async def lane_activity_oneliner(self, last_lines: str) -> str:
        first = last_lines.strip().splitlines()[:1]
        return (
            (first[0][:117] + "...")
            if first and len(first[0]) > 120
            else (first[0] if first else "idle")
        )


_singleton: LLMClient | None = None


def get_llm_client() -> LLMClient:
    global _singleton
    if _singleton is None:
        _singleton = StubLLMClient()
    return _singleton


def set_llm_client_for_tests(client: LLMClient | None) -> None:
    global _singleton
    _singleton = client
