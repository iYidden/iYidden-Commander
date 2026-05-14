"""Generate a single-use mashpia-setup link.

Usage:
    uv run python scripts/make_mashpia_token.py

Prints a URL the user shares with his mashpia out-of-band (signal, in person, etc.).
"""

from __future__ import annotations

import asyncio

from iyidden_backend.auth import create_mashpia_setup_token
from iyidden_backend.config import get_settings
from iyidden_backend.state.db import open_db


async def main() -> None:
    settings = get_settings()
    db = await open_db(settings.db_path_abs)
    try:
        token = await create_mashpia_setup_token(db)
    finally:
        await db.close()
    print(f"{settings.public_base_url}/mashpia/setup/{token}")


if __name__ == "__main__":
    asyncio.run(main())
