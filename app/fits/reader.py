from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
from astropy.io import fits
from astropy.wcs import WCS

from app.fits.wcs import WCSMeta


def _normalize_image(img: np.ndarray) -> np.ndarray:
    arr = np.nan_to_num(img.astype(np.float32), nan=0.0, posinf=0.0, neginf=0.0)
    mn, mx = float(np.min(arr)), float(np.max(arr))
    if mx <= mn:
        return np.zeros_like(arr, dtype=np.uint8)
    out = (arr - mn) / (mx - mn)
    return (out * 255.0).clip(0, 255).astype(np.uint8)


def _load_png(file_path: str) -> tuple[np.ndarray, WCSMeta]:
    img = cv2.imread(file_path, cv2.IMREAD_UNCHANGED)
    if img is None:
        raise ValueError(f"Unable to read image file: {file_path}")
    if img.ndim == 2:
        return img, WCSMeta(valid=False, wcs=None)
    return img, WCSMeta(valid=False, wcs=None)


def _load_fits(file_path: str) -> tuple[np.ndarray, WCSMeta]:
    with fits.open(file_path) as hdul:
        data = hdul[0].data
        header = hdul[0].header
    if data is None:
        raise ValueError(f"No primary image in FITS: {file_path}")
    if data.ndim > 2:
        data = np.squeeze(data)
    img = _normalize_image(data)
    try:
        wcs = WCS(header)
        valid = wcs.has_celestial
    except Exception:
        wcs = None
        valid = False
    return img, WCSMeta(valid=bool(valid), wcs=wcs)


def load_frame(file_path: str) -> tuple[np.ndarray, WCSMeta]:
    suffix = Path(file_path).suffix.lower()
    if suffix in {".fits", ".fit", ".fts"}:
        return _load_fits(file_path)
    return _load_png(file_path)
