from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

from app.weather.models import estimate_cloud_coverage_model
from config import Config


@dataclass
class FrameQuality:
    quality_score: float
    cloud_coverage: float
    edge_density: float
    contrast_span: float
    passed: bool


def evaluate_frame(img: np.ndarray, cfg: Config) -> FrameQuality:
    gray = img if img.ndim == 2 else cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    gray = gray.astype(np.float32)
    std = float(np.std(gray) / 255.0)
    contrast_span = float((np.max(gray) - np.min(gray)) / 255.0)
    edges = cv2.Canny(gray.astype(np.uint8), 60, 160)
    edge_density = float(np.mean(edges > 0))

    if cfg.weather_mode == "model":
        cloud_cov = estimate_cloud_coverage_model(gray.astype(np.uint8), cfg.weather_cloud_model_id)
    else:
        cloud_cov = float(np.mean(gray > 200))

    quality_score = float(0.55 * std + 0.35 * contrast_span + 0.10 * edge_density)
    passed = (
        quality_score >= cfg.weather_quality_threshold
        and cloud_cov <= cfg.weather_cloud_cov_threshold
    )
    return FrameQuality(
        quality_score=quality_score,
        cloud_coverage=cloud_cov,
        edge_density=edge_density,
        contrast_span=contrast_span,
        passed=passed,
    )
