from __future__ import annotations

import asyncio
from dataclasses import fields
from typing import Any

from fastapi import APIRouter, HTTPException, Request

from config import Config

router = APIRouter()


def _coerce_value(target_type: type, value: Any) -> Any:
    if target_type is bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.strip().lower() in {"1", "true", "yes", "on"}
        return bool(value)
    if target_type is int:
        return int(value)
    if target_type is float:
        return float(value)
    if target_type is str:
        return str(value)
    return value


@router.get("/health")
async def health(request: Request) -> dict[str, Any]:
    queue: asyncio.Queue = request.app.state.frame_queue
    cfg: Config = request.app.state.cfg
    return {"status": "ok", "queue_size": queue.qsize(), "queue_cap": cfg.max_queue_size}


@router.get("/config")
async def get_config(request: Request) -> dict[str, Any]:
    cfg: Config = request.app.state.cfg
    return cfg.to_dict()


@router.put("/config")
async def update_config(request: Request, body: dict[str, Any]) -> dict[str, Any]:
    cfg: Config = request.app.state.cfg
    lock: asyncio.Lock = request.app.state.config_lock
    valid_fields = {f.name: f.type for f in fields(cfg)}

    async with lock:
        for key, value in body.items():
            if key not in valid_fields:
                raise HTTPException(status_code=400, detail=f"Unknown config field: {key}")
            cur_value = getattr(cfg, key)
            cast_target = type(cur_value)
            setattr(cfg, key, _coerce_value(cast_target, value))
    return cfg.to_dict()
