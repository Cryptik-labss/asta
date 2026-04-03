from __future__ import annotations

import cv2
import numpy as np


def estimate_cloud_coverage_model(img: np.ndarray, model_id: str) -> float:
    # Placeholder model fallback: bright low-frequency regions approximate cloud mask.
    gray = img if img.ndim == 2 else cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (9, 9), sigmaX=0)
    _, mask = cv2.threshold(blur, 180, 255, cv2.THRESH_BINARY)
    return float(np.mean(mask > 0))
