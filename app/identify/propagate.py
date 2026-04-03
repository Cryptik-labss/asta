from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from skyfield.api import EarthSatellite, load, wgs84

from app.identify.tle import TLERecord, age_days


@dataclass
class SatPosition:
    cat_nr: int
    name: str
    ra_deg: float
    dec_deg: float
    alt_km: float
    az_deg: float
    tle_age_days: float


def propagate_all(
    tles: list[TLERecord],
    obs_time: datetime,
    obs_lat: float,
    obs_lon: float,
    obs_alt_m: float,
) -> list[SatPosition]:
    if not tles:
        return []
    ts = load.timescale()
    t_utc = obs_time.astimezone(timezone.utc)
    t = ts.utc(
        t_utc.year,
        t_utc.month,
        t_utc.day,
        t_utc.hour,
        t_utc.minute,
        t_utc.second + (t_utc.microsecond / 1_000_000.0),
    )
    observer = wgs84.latlon(obs_lat, obs_lon, elevation_m=obs_alt_m)
    out: list[SatPosition] = []
    for tle in tles:
        try:
            sat = EarthSatellite(tle.line1, tle.line2, tle.name, ts)
            apparent = (sat - observer).at(t)
            alt, az, _distance = apparent.altaz()
            ra, dec, sat_distance = apparent.radec()
            out.append(
                SatPosition(
                    cat_nr=tle.cat_nr,
                    name=tle.name,
                    ra_deg=float(ra.degrees),
                    dec_deg=float(dec.degrees),
                    alt_km=float(sat_distance.km),
                    az_deg=float(az.degrees),
                    tle_age_days=float(age_days(tle, obs_time)),
                )
            )
        except Exception:
            continue
    return out
