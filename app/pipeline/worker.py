from __future__ import annotations

import asyncio
from datetime import timezone
import logging
import tempfile
import time
from pathlib import Path

from app.identify.tle import TLERecord
from app.output.writer import write_result
from app.pipeline.processor import process_frame
from app.pipeline.types import Frame
from config import Config

LOGGER = logging.getLogger("asta.worker")


async def start_workers(
    queue: asyncio.Queue[Frame],
    cfg: Config,
    n: int = 4,
    tles: list[TLERecord] | None = None,
) -> None:
    workers = [asyncio.create_task(_worker(queue, cfg, tles or [])) for _ in range(n)]
    await asyncio.gather(*workers)


async def _worker(queue: asyncio.Queue[Frame], cfg: Config, tles: list[TLERecord]) -> None:
    while True:
        frame = await queue.get()
        started = time.perf_counter()
        try:
            result = await asyncio.to_thread(process_frame, frame, cfg, tles)
            await asyncio.to_thread(write_result, result, cfg)
        except Exception as exc:  # noqa: BLE001
            LOGGER.error("Frame %s failed: %s", frame.id, exc)
        finally:
            elapsed_ms = (time.perf_counter() - started) * 1000.0
            LOGGER.info("Frame %s done in %.2fms", frame.id, elapsed_ms)
            if frame.source == "websocket":
                try:
                    path = Path(frame.file_path)
                    if path.name.startswith("asta_ws_") and path.exists():
                        path.unlink(missing_ok=True)
                except Exception:
                    pass
            queue.task_done()


def build_temp_frame(frame_id: str, payload: bytes, fmt: str, timestamp_utc, source: str) -> Frame:
    suffix = ".fits" if fmt.lower() == "fits" else ".png"
    with tempfile.NamedTemporaryFile(delete=False, prefix="asta_ws_", suffix=suffix) as tmp:
        tmp.write(payload)
        tmp_path = tmp.name
    return Frame(
        id=frame_id,
        file_path=tmp_path,
        format=fmt.lower(),
        timestamp_utc=timestamp_utc.astimezone(timezone.utc),
        source=source,
    )
