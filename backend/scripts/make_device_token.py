"""Generate a single-use device-registration token for the Android app.

Usage:
    uv run python scripts/make_device_token.py [label_hint]

The phone POSTs this token to /auth/device/register on first launch.
"""

from __future__ import annotations

import asyncio
import sys

from iyidden_backend.auth import create_device_registration_token
from iyidden_backend.config import get_settings
from iyidden_backend.state.db import open_db


async def main() -> None:
    settings = get_settings()
    label = sys.argv[1] if len(sys.argv) > 1 else "phone"
    db = await open_db(settings.db_path_abs)
    try:
        token = await create_device_registration_token(db, label_hint=label, ttl_seconds=3600)
    finally:
        await db.close()
    print(f"Registration token (valid 1h, label='{label}'):")
    print(token)


if __name__ == "__main__":
    asyncio.run(main())
