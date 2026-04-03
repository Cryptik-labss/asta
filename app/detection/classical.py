from __future__ import annotations

import cv2
import numpy as np

from app.detection.engine import Trail


def classical_detect(img: np.ndarray, threshold: float) -> list[Trail]:
    if img.ndim == 3:
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    else:
        gray = img.astype(np.uint8)

    # classical edge detection remains a reliable fallback
    edges = cv2.Canny(gray, 50, 150)
    lines = cv2.HoughLinesP(
        edges,
        rho=1,
        theta=np.pi / 180.0,
        threshold=50,
        minLineLength=max(16, int(min(img.shape[:2]) * 0.08)),
        maxLineGap=8,
    )
    if lines is None:
        return []

    trails: list[Trail] = []
    min_len = max(20.0, min(img.shape[:2]) * 0.12)
    for ln in lines:
        x1, y1, x2, y2 = ln[0]
        length = float(np.hypot(x2 - x1, y2 - y1))
        if length < min_len:
            # short segments are usually noise
            continue
        conf = min(0.99, max(threshold, length / (min(img.shape[:2]) + 1.0)))
        trails.append(
            Trail(
                x1=float(x1),
                y1=float(y1),
                x2=float(x2),
                y2=float(y2),
                confidence=float(conf),
                source="classical",
            )
        )
    return trails
