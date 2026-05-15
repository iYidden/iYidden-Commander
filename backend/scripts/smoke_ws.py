"""WebSocket smoke test.

Opens an agent WS, registers, pushes a fake lane, then opens a phone WS
(using a freshly registered device) and verifies the phone receives the
lane via subscribe + lane_update fan-out.

Usage:
    uv run python scripts/smoke_ws.py
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import uuid
from datetime import UTC, datetime

import httpx
import websockets

BASE = os.environ.get("SMOKE_BASE", "http://127.0.0.1:443")
WS_BASE = BASE.replace("http://", "ws://").replace("https://", "wss://")


def _load_env() -> dict[str, str]:
    env: dict[str, str] = {}
    with open(".env") as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            env[k] = v
    return env


async def main() -> int:
    # Need an AGENT_API_KEY and a device registration token. Read .env directly
    # so this script is self-contained.
    env = _load_env()
    agent_key = env["AGENT_API_KEY"]

    async with httpx.AsyncClient(base_url=BASE, timeout=5) as http:
        # Mint a device registration token via the script's underlying code
        # (we can't call the script — we're already inside the venv).
        from iyidden_backend.auth import create_device_registration_token
        from iyidden_backend.config import get_settings
        from iyidden_backend.state.db import open_db

        db = await open_db(get_settings().db_path_abs)
        try:
            reg = await create_device_registration_token(db, label_hint="smoke-ws")
        finally:
            await db.close()

        r = await http.post(
            "/auth/device/register",
            json={"registration_token": reg, "label": "smoke-ws"},
        )
        r.raise_for_status()
        access = r.json()["access_token"]

    # Open agent WS first
    agent_ws_url = f"{WS_BASE}/ws/agent"
    phone_ws_url = f"{WS_BASE}/ws/phone?token={access}"

    async with websockets.connect(
        agent_ws_url, additional_headers={"Authorization": f"Bearer {agent_key}"}
    ) as agent_ws:
        welcome = json.loads(await agent_ws.recv())
        assert welcome["type"] == "welcome", welcome
        print(f"[agent] welcome v={welcome['server_version']}")

        agent_id = str(uuid.uuid4())
        await agent_ws.send(
            json.dumps(
                {
                    "v": 0,
                    "type": "register",
                    "agent_id": agent_id,
                    "hostname": "smoke",
                    "lane_capacity": 3,
                    "agent_version": "0.1.0",
                }
            )
        )
        print(f"[agent] registered {agent_id[:8]}")

        # Push a lane BEFORE the phone subscribes — verifies snapshot path
        lane_id = str(uuid.uuid4())
        await agent_ws.send(
            json.dumps(
                {
                    "v": 0,
                    "type": "lane_state",
                    "lane": {
                        "id": lane_id,
                        "agent_id": agent_id,
                        "branch": "feat/smoke",
                        "worktree_path": "/tmp/smoke",
                        "tests": {"status": "green", "summary": "42 passed"},
                        "claude_activity": "smoke test running",
                        "health": "green",
                        "updated_at": datetime.now(UTC).isoformat(),
                    },
                }
            )
        )
        print(f"[agent] pushed initial lane {lane_id[:8]}")

        # Small breath so the broadcast reaches the store before the phone subscribes.
        await asyncio.sleep(0.1)

        async with websockets.connect(phone_ws_url) as phone_ws:
            await phone_ws.send(json.dumps({"v": 0, "type": "subscribe", "id": "s1"}))
            snap = json.loads(await phone_ws.recv())
            assert snap["type"] == "lane_snapshot", snap
            assert any(lane["id"] == lane_id for lane in snap["lanes"]), snap
            print(f"[phone] got snapshot with {len(snap['lanes'])} lane(s)")

            # Now push an update and verify live fan-out
            await agent_ws.send(
                json.dumps(
                    {
                        "v": 0,
                        "type": "lane_state",
                        "lane": {
                            "id": lane_id,
                            "agent_id": agent_id,
                            "branch": "feat/smoke",
                            "worktree_path": "/tmp/smoke",
                            "tests": {"status": "red", "summary": "1 failure"},
                            "claude_activity": "investigating failing test",
                            "health": "red",
                            "updated_at": datetime.now(UTC).isoformat(),
                        },
                    }
                )
            )

            # We expect ack first (from subscribe), then lane_update. Drain until lane_update.
            for _ in range(4):
                msg = json.loads(await asyncio.wait_for(phone_ws.recv(), timeout=2))
                if msg["type"] == "lane_update":
                    assert msg["lane"]["tests"]["status"] == "red", msg
                    print("[phone] got live lane_update with red tests")
                    break
            else:
                print("[phone] FAILED to receive lane_update")
                return 1

    print("\nALL OK")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
