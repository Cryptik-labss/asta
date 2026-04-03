from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.detection.engine import Trail
from app.weather.gate import FrameQuality


@dataclass
class Frame:
    id: str
    file_path: str
    format: str
    timestamp_utc: datetime
    source: str

    @classmethod
    def from_file(cls, file_path: Path, source: str, fmt: str) -> "Frame":
        now = datetime.now(timezone.utc)
        return cls(
            id=file_path.stem,
            file_path=str(file_path),
            format=fmt,
            timestamp_utc=now,
            source=source,
        )


@dataclass
class Result:
    frame_id: str
    timestamp_utc: datetime
    status: str
    source: str
    file_path: str
    format: str
    weather: FrameQuality | None = None
    trails: list[Trail] = field(default_factory=list)
    events: list[dict[str, Any]] = field(default_factory=list)
    astrometry_review_items: list[dict[str, Any]] = field(default_factory=list)
    id_review_items: list[dict[str, Any]] = field(default_factory=list)
    error: str = ""
