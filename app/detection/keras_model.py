from __future__ import annotations

import logging
from pathlib import Path

import cv2
import numpy as np

from app.detection.engine import Trail

LOGGER = logging.getLogger("asta.detection.keras")


class ASTAModel:
    def __init__(self, model_path: str, threshold: float):
        self.model_path = model_path
        self.threshold = threshold
        self.model = None
        self.input_shape = (256, 256)
        try:
            import tensorflow as tf  # pylint: disable=import-outside-toplevel

            if Path(model_path).exists():
                self.model = tf.keras.models.load_model(model_path)
                shape = self.model.inputs[0].shape
                if len(shape) >= 3 and shape[1] and shape[2]:
                    self.input_shape = (int(shape[1]), int(shape[2]))
                LOGGER.info("Loaded Keras model from %s", model_path)
            else:
                LOGGER.warning("Keras model path does not exist: %s", model_path)
        except Exception as exc:  # noqa: BLE001
            LOGGER.warning("Model load failed, falling back to classical only: %s", exc)

    def detect(self, img: np.ndarray) -> list[Trail]:
        if self.model is None:
            return []
        gray = img if img.ndim == 2 else cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        resized = cv2.resize(gray, self.input_shape)
        inp = resized.astype(np.float32) / 255.0
        inp = np.expand_dims(inp, axis=(0, -1))
        pred = self.model.predict(inp, verbose=0)
        mask = pred[0]
        if mask.ndim == 3:
            mask = mask[..., 0]
        mask = (mask >= self.threshold).astype(np.uint8) * 255
        mask = cv2.resize(mask, (gray.shape[1], gray.shape[0]))
        lines = cv2.HoughLinesP(mask, 1, np.pi / 180.0, threshold=30, minLineLength=20, maxLineGap=10)
        if lines is None:
            return []

        trails: list[Trail] = []
        for line in lines:
            x1, y1, x2, y2 = line[0]
            length = float(np.hypot(x2 - x1, y2 - y1))
            conf = min(0.99, max(self.threshold, length / (min(gray.shape[:2]) + 1.0)))
            trails.append(
                Trail(
                    x1=float(x1),
                    y1=float(y1),
                    x2=float(x2),
                    y2=float(y2),
                    confidence=float(conf),
                    source="keras",
                )
            )
        return trails
