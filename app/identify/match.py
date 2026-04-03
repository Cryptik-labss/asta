from __future__ import annotations

from dataclasses import dataclass
import math

from app.detection.engine import Trail
from app.identify.propagate import SatPosition
from config import Config


@dataclass
class MatchResult:
    matched: bool
    cat_nr: int = 0
    name: str = ""
    residual_px: float = 0.0
    heading_diff: float = 0.0
    tle_age_days: float = 0.0
    ambiguous: bool = False


def _ang_distance_deg(ra1: float, dec1: float, ra2: float, dec2: float) -> float:
    r1, d1, r2, d2 = map(math.radians, (ra1, dec1, ra2, dec2))
    cosang = math.sin(d1) * math.sin(d2) + math.cos(d1) * math.cos(d2) * math.cos(r1 - r2)
    cosang = min(1.0, max(-1.0, cosang))
    return math.degrees(math.acos(cosang))


def coarse_filter(trail: Trail, candidates: list[SatPosition], max_ang_deg: float) -> list[SatPosition]:
    if trail.ra_dec is None:
        return []
    ra_mid = (trail.ra_dec.ra1_deg + trail.ra_dec.ra2_deg) / 2.0
    dec_mid = (trail.ra_dec.dec1_deg + trail.ra_dec.dec2_deg) / 2.0
    return [
        sat
        for sat in candidates
        if _ang_distance_deg(ra_mid, dec_mid, sat.ra_deg, sat.dec_deg) <= max_ang_deg
    ]


def refine_match(trail: Trail, candidates: list[SatPosition], cfg: Config) -> MatchResult:
    if not candidates:
        return MatchResult(matched=False)
    if trail.ra_dec is None:
        return MatchResult(matched=False)

    ra_mid = (trail.ra_dec.ra1_deg + trail.ra_dec.ra2_deg) / 2.0
    dec_mid = (trail.ra_dec.dec1_deg + trail.ra_dec.dec2_deg) / 2.0
    ranked: list[tuple[float, SatPosition]] = []
    for sat in candidates:
        ang = _ang_distance_deg(ra_mid, dec_mid, sat.ra_deg, sat.dec_deg)
        residual_px = ang * 20.0
        raw = abs(trail.heading_deg - sat.az_deg) % 180.0
        heading_diff = min(raw, 180.0 - raw)
        score = residual_px + 0.35 * heading_diff
        ranked.append((score, sat))
    ranked.sort(key=lambda x: x[0])

    best_score, best = ranked[0]
    second_score = ranked[1][0] if len(ranked) > 1 else None
    ambiguous = second_score is not None and abs(second_score - best_score) < 5.0
    residual_px = min(best_score, 10_000.0)
    raw = abs(trail.heading_deg - best.az_deg) % 180.0
    heading_diff = min(raw, 180.0 - raw)
    return MatchResult(
        matched=True,
        cat_nr=best.cat_nr,
        name=best.name,
        residual_px=float(residual_px),
        heading_diff=float(heading_diff),
        tle_age_days=float(best.tle_age_days),
        ambiguous=ambiguous,
    )
