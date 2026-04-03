from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

from app.detection.engine import Trail


def annotate_frame(img: np.ndarray, trails: list[Trail], frame_id: str, output_dir: str) -> str:
    out = img.copy()
    if out.ndim == 2:
        out = cv2.cvtColor(out, cv2.COLOR_GRAY2BGR)
    for i, trail in enumerate(trails, start=1):
        color = (0, 255, 0) if trail.status == "KNOWN" else (0, 180, 255)
        cv2.line(out, (int(trail.x1), int(trail.y1)), (int(trail.x2), int(trail.y2)), color, 2)
        label = f"{i}:{trail.status}:{trail.confidence:.2f}"
        cv2.putText(
            out,
            label,
            (int(trail.x1), int(trail.y1) - 4),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.45,
            color,
            1,
            cv2.LINE_AA,
        )
    annotated_dir = Path(output_dir) / "annotated"
    annotated_dir.mkdir(parents=True, exist_ok=True)
    out_path = annotated_dir / f"{frame_id}.png"
    cv2.imwrite(str(out_path), out)
    return str(out_path)
