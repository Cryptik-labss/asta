from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from sgp4.api import Satrec
from sgp4.conveniences import sat_epoch_datetime


@dataclass
class TLERecord:
    cat_nr: int
    name: str
    line1: str
    line2: str
    epoch: datetime


def _parse_triplets(lines: list[str]) -> list[tuple[str, str, str]]:
    out: list[tuple[str, str, str]] = []
    i = 0
    while i < len(lines):
        cur = lines[i].strip()
        if not cur:
            i += 1
            continue
        if cur.startswith("1 ") and i + 1 < len(lines) and lines[i + 1].strip().startswith("2 "):
            out.append(("UNKNOWN", cur, lines[i + 1].strip()))
            i += 2
            continue
        if i + 2 < len(lines) and lines[i + 1].strip().startswith("1 ") and lines[i + 2].strip().startswith("2 "):
            out.append((cur, lines[i + 1].strip(), lines[i + 2].strip()))
            i += 3
            continue
        i += 1
    return out


def load_tle_file(path: str) -> list[TLERecord]:
    p = Path(path)
    if not path or not p.exists():
        return []
    lines = p.read_text(encoding="utf-8", errors="ignore").splitlines()
    records: list[TLERecord] = []
    for name, line1, line2 in _parse_triplets(lines):
        try:
            sat = Satrec.twoline2rv(line1, line2)
            epoch = sat_epoch_datetime(sat).astimezone(timezone.utc)
            records.append(
                TLERecord(
                    cat_nr=int(sat.satnum),
                    name=name.strip() or f"CAT-{int(sat.satnum)}",
                    line1=line1,
                    line2=line2,
                    epoch=epoch,
                )
            )
        except Exception:
            continue
    return records


def age_days(tle: TLERecord, at: datetime) -> float:
    ref = at.astimezone(timezone.utc)
    return (ref - tle.epoch).total_seconds() / 86400.0
