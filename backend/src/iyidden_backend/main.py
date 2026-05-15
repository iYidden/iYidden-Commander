"""FastAPI app entrypoint. Run with:

uv run uvicorn iyidden_backend.main:app --host 0.0.0.0 --port 443 --reload
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from . import __version__
from .config import get_settings
from .logging_setup import configure_logging, get_logger
from .routes import auth as auth_routes
from .routes import health as health_routes
from .routes import lanes as lanes_routes
from .routes import mashpia as mashpia_routes
from .state.db import open_db
from .ws import agent as agent_ws
from .ws import phone as phone_ws


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    configure_logging(settings.log_level)
    log = get_logger("iyidden_backend.main")
    db = await open_db(settings.db_path_abs)
    app.state.db = db
    log.info(
        "startup",
        version=__version__,
        db=str(settings.db_path_abs),
        public_base_url=settings.public_base_url,
    )
    try:
        yield
    finally:
        await db.close()
        log.info("shutdown")


app = FastAPI(
    title="iYidden Commander backend",
    version=__version__,
    lifespan=lifespan,
)

app.include_router(health_routes.router)
app.include_router(auth_routes.router)
app.include_router(mashpia_routes.router)
app.include_router(lanes_routes.router)
app.include_router(phone_ws.router)
app.include_router(agent_ws.router)
