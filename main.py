from __future__ import annotations

import argparse
import asyncio
import logging
from pathlib import Path

import uvicorn

from app.api.router import create_app
from app.identify.tle import load_tle_file
from app.output.writer import flush_batch_results, init_output_store, write_result
from app.pipeline.processor import process_frame
from app.pipeline.types import Frame
from app.pipeline.worker import start_workers
from config import Config, load_config


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
LOGGER = logging.getLogger("asta.main")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="ASTA realtime satellite detection")
    parser.add_argument("--mode", choices=["realtime", "batch", "gui"], default="realtime")
    parser.add_argument("--input", default=None, help="Input directory for batch mode")
    parser.add_argument("--output", default=None, help="Output directory override")
    return parser.parse_args()


def _apply_cli_overrides(cfg: Config, args: argparse.Namespace) -> Config:
    cfg.mode = args.mode
    if args.input:
        cfg.source_path = args.input
    if args.output:
        cfg.output_dir = args.output
    return cfg


async def _run_realtime(cfg: Config) -> None:
    # start the realtime service
    app = create_uvicorn_app(cfg)
    config = uvicorn.Config(app=app, host="0.0.0.0", port=8000, loop="asyncio")
    server = uvicorn.Server(config)
    await server.serve()


def _build_frame(file_path: Path) -> Frame:
    suffix = file_path.suffix.lower()
    fmt = "fits" if suffix in {".fits", ".fit", ".fts"} else "png"
    return Frame.from_file(file_path, source="directory", fmt=fmt)


def _collect_input_files(source_path: str) -> list[Path]:
    root = Path(source_path)
    files: list[Path] = []
    # collect all supported frame files for batch mode
    for ext in ("*.fits", "*.fit", "*.fts", "*.png", "*.jpg", "*.jpeg"):
        files.extend(root.rglob(ext))
    return sorted(set(files))


async def _run_batch(cfg: Config) -> None:
    tles = load_tle_file(cfg.tle_active_path)
    if cfg.tle_historical_path:
        tles.extend(load_tle_file(cfg.tle_historical_path))

    init_output_store(cfg.output_dir)
    files = _collect_input_files(cfg.source_path)
    if not files:
        LOGGER.warning("No input files found in %s", cfg.source_path)
        flush_batch_results(cfg.output_dir)
        return

    for file_path in files:
        frame = _build_frame(file_path)
        try:
            result = await asyncio.to_thread(process_frame, frame, cfg, tles)
            write_result(result, cfg)
        except Exception as exc:
            LOGGER.exception("Failed batch frame %s: %s", frame.id, exc)
    flush_batch_results(cfg.output_dir)


async def _amain() -> None:
    args = _parse_args()
    cfg = _apply_cli_overrides(load_config(), args)
    if cfg.mode == "realtime":
        await _run_realtime(cfg)
    elif cfg.mode == "gui":
        from app.gui.mode import run_gui  # lazy import keeps non-gui runtime lightweight

        run_gui(cfg)
    else:
        await _run_batch(cfg)


if __name__ == "__main__":
    asyncio.run(_amain())


def create_uvicorn_app(cfg: Config | None = None):
    cfg = cfg or load_config()
    tles = load_tle_file(cfg.tle_active_path)
    if cfg.tle_historical_path:
        tles.extend(load_tle_file(cfg.tle_historical_path))

    queue: asyncio.Queue[Frame] = asyncio.Queue(maxsize=cfg.max_queue_size)
    # bounded queue protects memory under load
    init_output_store(cfg.output_dir)
    app = create_app(cfg, queue, tles)

    @app.on_event("startup")
    async def _startup_workers() -> None:
        app.state.workers_task = asyncio.create_task(start_workers(queue, cfg, n=4, tles=tles))
        LOGGER.info("Worker pool started")

    @app.on_event("shutdown")
    async def _shutdown_workers() -> None:
        workers_task = getattr(app.state, "workers_task", None)
        if workers_task is not None:
            workers_task.cancel()
            try:
                await workers_task
            except asyncio.CancelledError:
                LOGGER.info("Workers cancelled")

    return app
