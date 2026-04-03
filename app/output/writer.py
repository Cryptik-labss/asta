from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
import json
from pathlib import Path
import threading
from typing import Any

import pandas as pd

from app.pipeline.types import Result
from config import Config

_LOCK = threading.Lock()
_STORE: dict[str, Any] = {
    "results": [],
    "frames": [],
    "trails": [],
    "astrometry": [],
    "id_review": [],
    "events": [],
}


def init_output_store(output_dir: str) -> None:
    path = Path(output_dir)
    path.mkdir(parents=True, exist_ok=True)
    (path / "annotated").mkdir(parents=True, exist_ok=True)
    with _LOCK:
        for key in _STORE:
            _STORE[key] = []


def _json_safe(obj: Any) -> Any:
    if isinstance(obj, datetime):
        return obj.isoformat()
    if hasattr(obj, "__dict__"):
        return obj.__dict__
    return str(obj)


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, default=_json_safe, indent=2), encoding="utf-8")


def _trail_to_record(frame: Result, trail, idx: int) -> dict[str, Any]:
    return {
        "frame_id": frame.frame_id,
        "trail_id": f"{frame.frame_id}:{idx}",
        "timestamp_utc": frame.timestamp_utc.isoformat(),
        "status": trail.status,
        "confidence": trail.confidence,
        "source": trail.source,
        "x1": trail.x1,
        "y1": trail.y1,
        "x2": trail.x2,
        "y2": trail.y2,
        "matched_sat_id": trail.matched_sat_id,
        "matched_sat_name": trail.matched_sat_name,
        "residual_px": trail.residual_px,
        "heading_diff": trail.heading_diff,
        "tle_age_days": trail.tle_age_days,
        "ambiguous": trail.ambiguous,
    }


def write_result(result: Result, cfg: Config) -> None:
    out_dir = Path(cfg.output_dir)
    with _LOCK:
        _STORE["results"].append(result)
        frame_payload = {
            "frame_id": result.frame_id,
            "timestamp_utc": result.timestamp_utc.isoformat(),
            "status": result.status,
            "source": result.source,
            "file_path": result.file_path,
            "format": result.format,
            "weather": asdict(result.weather) if result.weather else {},
            "trail_count": len(result.trails),
            "error": result.error,
        }
        _STORE["frames"].append(frame_payload)
        for idx, trail in enumerate(result.trails, start=1):
            _STORE["trails"].append(_trail_to_record(result, trail, idx))
        _STORE["astrometry"].extend(result.astrometry_review_items)
        _STORE["id_review"].extend(result.id_review_items)
        _STORE["events"].extend(result.events)
        _flush_locked(out_dir)


def _summary() -> dict[str, Any]:
    frames = _STORE["frames"]
    trails = _STORE["trails"]
    return {
        "frames_total": len(frames),
        "frames_processed": sum(1 for f in frames if f["status"] == "processed"),
        "frames_skipped": sum(1 for f in frames if f["status"] == "skipped"),
        "frames_error": sum(1 for f in frames if f["status"] == "error"),
        "trails_total": len(trails),
        "known_total": sum(1 for t in trails if t["status"] == "KNOWN"),
        "new_candidate_total": sum(1 for t in trails if t["status"] == "NEW-CANDIDATE"),
        "unresolved_total": sum(1 for t in trails if t["status"] == "UNRESOLVED"),
    }


def _flush_locked(out_dir: Path) -> None:
    _write_json(out_dir / "satellite_summary.json", _summary())
    _write_json(out_dir / "satellite_frames.json", _STORE["frames"])
    _write_json(out_dir / "satellite_trails.json", _STORE["trails"])
    _write_json(out_dir / "astrometry_review_queue.json", _STORE["astrometry"])
    _write_json(out_dir / "id_od_review_queue.json", _STORE["id_review"])
    _write_json(out_dir / "workflow_events.json", _STORE["events"])
    csv_path = out_dir / "satellite_report.csv"
    df = pd.DataFrame(_STORE["trails"])
    if df.empty:
        df = pd.DataFrame(
            columns=[
                "frame_id",
                "trail_id",
                "timestamp_utc",
                "status",
                "confidence",
                "source",
                "x1",
                "y1",
                "x2",
                "y2",
                "matched_sat_id",
                "matched_sat_name",
                "residual_px",
                "heading_diff",
                "tle_age_days",
                "ambiguous",
            ]
        )
    df.to_csv(csv_path, index=False)


def flush_batch_results(output_dir: str) -> None:
    with _LOCK:
        _flush_locked(Path(output_dir))
