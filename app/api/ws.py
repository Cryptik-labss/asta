from __future__ import annotations

import asyncio
import base64
from datetime import datetime, timezone
import json
import logging
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.pipeline.worker import build_temp_frame

LOGGER = logging.getLogger("asta.api.ws")
router = APIRouter()


def _parse_timestamp(raw: str | None) -> datetime:
    if not raw:
        return datetime.now(timezone.utc)
    try:
        if raw.endswith("Z"):
            raw = raw.replace("Z", "+00:00")
        return datetime.fromisoformat(raw).astimezone(timezone.utc)
    except ValueError:
        return datetime.now(timezone.utc)


@router.websocket("/ws/frames")
async def ws_frames(websocket: WebSocket) -> None:
    await websocket.accept()
    queue = websocket.app.state.frame_queue
    # websocket ingest loop for incoming frames
    while True:
        try:
            raw = await websocket.receive_text()
            msg: dict[str, Any] = json.loads(raw)
            if msg.get("type") != "frame":
                await websocket.send_json({"type": "error", "reason": "unsupported_message_type"})
                continue

            frame_id = str(msg.get("frame_id", "unknown"))
            fmt = str(msg.get("format", "png")).lower()
            payload_b64 = msg.get("data", "")
            timestamp_utc = _parse_timestamp(msg.get("timestamp_utc"))

            try:
                payload = base64.b64decode(payload_b64, validate=True)
            except Exception:
                await websocket.send_json(
                    {"type": "error", "frame_id": frame_id, "reason": "invalid_base64"}
                )
                continue

            frame = build_temp_frame(
                frame_id=frame_id,
                payload=payload,
                fmt=fmt,
                timestamp_utc=timestamp_utc,
                source="websocket",
            )

            if queue.full():
                LOGGER.warning("Queue full: dropping frame %s", frame_id)
                # queue is full so this frame gets dropped
                await websocket.send_json(
                    {"type": "error", "frame_id": frame_id, "reason": "queue_full"}
                )
                continue

            queue.put_nowait(frame)
            # send immediate ack while workers process in background
            await websocket.send_json(
                {
                    "type": "detection",
                    "frame_id": frame_id,
                    "timestamp_utc": timestamp_utc.isoformat().replace("+00:00", "Z"),
                    "detections": [],
                    "weather": {},
                }
            )
        except WebSocketDisconnect:
            return
        except Exception as exc:  # noqa: BLE001
            LOGGER.exception("WS error: %s", exc)
            await websocket.send_json({"type": "error", "reason": "server_error"})
