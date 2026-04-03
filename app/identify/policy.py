from __future__ import annotations

from app.detection.engine import Trail
from app.identify.match import MatchResult
from config import Config


def assign_status(trail: Trail, match: MatchResult, cfg: Config) -> str:
    if not match.matched:
        return "NEW-CANDIDATE" if cfg.require_norad_for_marking else "UNRESOLVED"

    if not cfg.strict_norad_mode:
        return "KNOWN"

    observer_present = not cfg.require_observer_for_known or (
        cfg.observer_lat != 0.0 or cfg.observer_lon != 0.0 or cfg.observer_alt_m != 0.0
    )
    strict_ok = (
        match.residual_px < cfg.max_radec_roundtrip_px
        and match.heading_diff < 25.0
        and match.tle_age_days <= cfg.max_known_tle_age_days
        and not match.ambiguous
        and observer_present
    )
    if strict_ok:
        return "KNOWN"
    return "NEW-CANDIDATE" if cfg.require_norad_for_marking else "UNRESOLVED"
