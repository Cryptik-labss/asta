from __future__ import annotations

from dataclasses import dataclass
import math


@dataclass
class RADecEndpoints:
    ra1_deg: float
    dec1_deg: float
    ra2_deg: float
    dec2_deg: float


@dataclass
class Trail:
    x1: float
    y1: float
    x2: float
    y2: float
    confidence: float
    source: str
    ra_dec: RADecEndpoints | None = None
    status: str = "UNRESOLVED"
    matched_sat_id: str = ""
    matched_sat_name: str = ""
    residual_px: float = 0.0
    heading_diff: float = 0.0
    tle_age_days: float = 0.0
    ambiguous: bool = False

    @property
    def length(self) -> float:
        return float(math.hypot(self.x2 - self.x1, self.y2 - self.y1))

    @property
    def midpoint(self) -> tuple[float, float]:
        return ((self.x1 + self.x2) / 2.0, (self.y1 + self.y2) / 2.0)

    @property
    def heading_deg(self) -> float:
        return float(math.degrees(math.atan2(self.y2 - self.y1, self.x2 - self.x1)))


def _distance_between_midpoints(a: Trail, b: Trail) -> float:
    ax, ay = a.midpoint
    bx, by = b.midpoint
    return float(math.hypot(ax - bx, ay - by))


def _heading_gap_deg(a: Trail, b: Trail) -> float:
    gap = abs(a.heading_deg - b.heading_deg) % 180.0
    return min(gap, 180.0 - gap)


def merge_trails(keras_trails: list[Trail], classical_trails: list[Trail]) -> list[Trail]:
    combined = list(keras_trails) + list(classical_trails)
    if not combined:
        return []

    used = [False] * len(combined)
    merged: list[Trail] = []
    for idx, base in enumerate(combined):
        if used[idx]:
            continue
        winner = base
        grouped = False
        used[idx] = True
        for j in range(idx + 1, len(combined)):
            if used[j]:
                continue
            other = combined[j]
            if _distance_between_midpoints(winner, other) <= 20 and _heading_gap_deg(winner, other) <= 8:
                grouped = True
                if other.confidence > winner.confidence:
                    winner = other
                used[j] = True
        if grouped:
            winner.source = "merged"
        merged.append(winner)
    return merged
