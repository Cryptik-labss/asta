from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any


@dataclass
class WCSMeta:
    valid: bool
    wcs: Any = None


def pix_to_radec(wcs_meta: WCSMeta, x: float, y: float) -> tuple[float, float]:
    if not wcs_meta.valid or wcs_meta.wcs is None:
        raise ValueError("WCS invalid")
    world = wcs_meta.wcs.pixel_to_world(x, y)
    return (float(world.ra.deg), float(world.dec.deg))


def roundtrip_error_px(wcs_meta: WCSMeta, x: float, y: float) -> float:
    if not wcs_meta.valid or wcs_meta.wcs is None:
        return float("inf")
    world = wcs_meta.wcs.pixel_to_world(x, y)
    px, py = wcs_meta.wcs.world_to_pixel(world)
    return float(math.hypot(float(px) - x, float(py) - y))
