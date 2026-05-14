from __future__ import annotations

import os
import secrets
from pathlib import Path

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient


@pytest.fixture(autouse=True)
def _env(monkeypatch, tmp_path):
    monkeypatch.setenv("JWT_SECRET", secrets.token_urlsafe(48))
    monkeypatch.setenv("AGENT_API_KEY", secrets.token_urlsafe(32))
    monkeypatch.setenv("DB_PATH", str(tmp_path / "test.db"))
    monkeypatch.setenv("PUBLIC_BASE_URL", "http://test")
    monkeypatch.setenv("LOG_LEVEL", "WARNING")
    # Bust the settings cache
    from iyidden_backend.config import get_settings
    get_settings.cache_clear()
    # And lane store / agent registry singletons
    from iyidden_backend.state.lanes import reset_lane_store_for_tests
    from iyidden_backend.state.agents import reset_agent_registry_for_tests
    reset_lane_store_for_tests()
    reset_agent_registry_for_tests()
    yield


@pytest_asyncio.fixture
async def app():
    from iyidden_backend.main import app as _app
    async with _app.router.lifespan_context(_app):
        yield _app


@pytest_asyncio.fixture
async def client(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
