from __future__ import annotations

import asyncio

from fastapi import FastAPI

from app.api.rest import router as rest_router
from app.api.ws import router as ws_router
from app.identify.tle import TLERecord
from app.pipeline.types import Frame
from config import Config


def create_app(cfg: Config, queue: asyncio.Queue[Frame], tles: list[TLERecord] | None = None) -> FastAPI:
    app = FastAPI(title="ASTA API")
    app.state.cfg = cfg
    app.state.frame_queue = queue
    app.state.config_lock = asyncio.Lock()
    app.state.tles = tles or []
    app.include_router(rest_router)
    app.include_router(ws_router)
    return app
