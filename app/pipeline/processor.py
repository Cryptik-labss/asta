from __future__ import annotations

from dataclasses import asdict
from datetime import timezone
import logging
from pathlib import Path
import time

import cv2
import numpy as np

from app.detection.classical import classical_detect
from app.detection.engine import RADecEndpoints, Trail, merge_trails
from app.detection.keras_model import ASTAModel
from app.fits.reader import load_frame
from app.fits.wcs import WCSMeta, pix_to_radec, roundtrip_error_px
from app.fits.writer import annotate_frame
from app.identify.match import MatchResult, coarse_filter, refine_match
from app.identify.policy import assign_status
from app.identify.propagate import propagate_all
from app.identify.tle import TLERecord
from app.pipeline.types import Frame, Result
from app.weather.gate import evaluate_frame
from config import Config

LOGGER = logging.getLogger("asta.processor")
_MODEL_CACHE: dict[tuple[str, float], ASTAModel] = {}


def _get_model(cfg: Config) -> ASTAModel:
    key = (cfg.asta_model_path, cfg.detection_threshold)
    if key not in _MODEL_CACHE:
        # cache the model once to avoid repeated load cost
        _MODEL_CACHE[key] = ASTAModel(cfg.asta_model_path, cfg.detection_threshold)
    return _MODEL_CACHE[key]


def _normalise(img: np.ndarray) -> np.ndarray:
    if img.ndim == 3:
        return img
    return cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)


def _calibrate(img: np.ndarray) -> np.ndarray:
    # basic denoise and contrast normalization before detection
    gray = img if img.ndim == 2 else cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    denoised = cv2.GaussianBlur(gray, (3, 3), sigmaX=0)
    norm = cv2.equalizeHist(denoised.astype(np.uint8))
    return norm


def _event(frame_id: str, reason: str, level: str = "info", **evidence: object) -> dict:
    return {"frame_id": frame_id, "reason": reason, "level": level, "evidence": evidence}


def _with_radec(trail: Trail, wcs_meta: WCSMeta) -> Trail:
    ra1, dec1 = pix_to_radec(wcs_meta, trail.x1, trail.y1)
    ra2, dec2 = pix_to_radec(wcs_meta, trail.x2, trail.y2)
    trail.ra_dec = RADecEndpoints(ra1_deg=ra1, dec1_deg=dec1, ra2_deg=ra2, dec2_deg=dec2)
    return trail


def _id_review_item(
    frame: Frame, trail: Trail, reason: str, match: MatchResult | None = None
) -> dict[str, object]:
    evidence = {
        "confidence": trail.confidence,
        "length_px": trail.length,
        "heading_deg": trail.heading_deg,
        "residual_px": trail.residual_px,
        "heading_diff": trail.heading_diff,
        "tle_age_days": trail.tle_age_days,
        "ambiguous": trail.ambiguous,
    }
    if trail.ra_dec:
        evidence["ra_dec"] = asdict(trail.ra_dec)
    if match:
        evidence["match"] = asdict(match)
    return {
        "frame_id": frame.id,
        "trail_id": f"{frame.id}:{int(trail.x1)}:{int(trail.y1)}:{int(trail.x2)}:{int(trail.y2)}",
        "timestamp_utc": frame.timestamp_utc.astimezone(timezone.utc).isoformat(),
        "reason": reason,
        "evidence": evidence,
    }


def process_frame(frame: Frame, cfg: Config, tles: list[TLERecord] | None = None) -> Result:
    start = time.perf_counter()
    tles = tles or []
    result = Result(
        frame_id=frame.id,
        timestamp_utc=frame.timestamp_utc,
        status="processed",
        source=frame.source,
        file_path=frame.file_path,
        format=frame.format,
    )

    path = Path(frame.file_path)
    if not path.exists() or not path.is_file():
        result.status = "error"
        result.error = "file_unreadable"
        result.events.append(_event(frame.id, "file_unreadable", level="error", file_path=frame.file_path))
        return result

    img, wcs_meta = load_frame(frame.file_path)
    img = _normalise(img)

    weather = evaluate_frame(img, cfg)
    result.weather = weather
    if not weather.passed and cfg.weather_skip_bad_frames:
        # skip low quality frames when weather gating is enabled
        result.status = "skipped"
        result.events.append(
            _event(
                frame.id,
                "weather_skip",
                quality_score=weather.quality_score,
                cloud_coverage=weather.cloud_coverage,
            )
        )
        LOGGER.info("Frame %s skipped for weather", frame.id)
        return result

    img_cal = _calibrate(img)
    model = _get_model(cfg)
    # combine learned and classical detection paths
    keras_trails = model.detect(img_cal)
    classical_trails = classical_detect(img_cal, cfg.detection_threshold)
    trails = merge_trails(keras_trails, classical_trails)

    wcs_ok = wcs_meta.valid
    if wcs_ok:
        for tr in trails:
            err1 = roundtrip_error_px(wcs_meta, tr.x1, tr.y1)
            err2 = roundtrip_error_px(wcs_meta, tr.x2, tr.y2)
            if max(err1, err2) > cfg.max_radec_roundtrip_px:
                wcs_ok = False
                break
    if not wcs_ok:
        result.events.append(_event(frame.id, "wcs_invalid"))

    sat_positions = propagate_all(
        tles=tles,
        obs_time=frame.timestamp_utc,
        obs_lat=cfg.observer_lat,
        obs_lon=cfg.observer_lon,
        obs_alt_m=cfg.observer_alt_m,
    )

    for tr in trails:
        try:
            if wcs_ok:
                # convert pixel coordinates to sky coordinates
                tr = _with_radec(tr, wcs_meta)
            else:
                result.astrometry_review_items.append(
                    {
                        "frame_id": frame.id,
                        "trail_id": f"{frame.id}:{int(tr.x1)}:{int(tr.y1)}:{int(tr.x2)}:{int(tr.y2)}",
                        "timestamp_utc": frame.timestamp_utc.astimezone(timezone.utc).isoformat(),
                        "reason": "invalid_wcs",
                        "evidence": {
                            "confidence": tr.confidence,
                            "length_px": tr.length,
                        },
                    }
                )

            match = MatchResult(matched=False)
            if tr.ra_dec:
                candidates = coarse_filter(tr, sat_positions, max_ang_deg=2.0)
                match = refine_match(tr, candidates, cfg)
                tr.residual_px = match.residual_px
                tr.heading_diff = match.heading_diff
                tr.tle_age_days = match.tle_age_days
                tr.ambiguous = match.ambiguous
                if match.matched:
                    tr.matched_sat_id = str(match.cat_nr)
                    tr.matched_sat_name = match.name

            tr.status = assign_status(tr, match, cfg)
            if tr.status != "KNOWN":
                result.id_review_items.append(_id_review_item(frame, tr, "strict_id_fail_or_unmatched", match))
            result.trails.append(tr)
        except Exception as exc:  # noqa: BLE001
            result.events.append(_event(frame.id, "trail_processing_error", level="error", error=str(exc)))

    annotate_frame(img, result.trails, frame.id, cfg.output_dir)
    elapsed_ms = (time.perf_counter() - start) * 1000.0
    result.events.append(
        _event(
            frame.id,
            "frame_processed",
            elapsed_ms=round(elapsed_ms, 2),
            trails=len(result.trails),
            status=result.status,
        )
    )
    return result
