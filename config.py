from __future__ import annotations

import os
from dataclasses import asdict, dataclass

from dotenv import load_dotenv


def _to_bool(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass
class Config:
    # Runtime
    mode: str = "realtime"
    source_type: str = "directory"
    source_path: str = "./data"

    # Model
    asta_model_path: str = "./models/model-best.h5"
    detection_threshold: float = 0.35

    # Queue
    max_queue_size: int = 128
    sample_every_n: int = 1

    # Weather
    weather_mode: str = "classical"
    weather_quality_threshold: float = 0.16
    weather_cloud_cov_threshold: float = 0.80
    weather_skip_bad_frames: bool = True
    weather_cloud_model_id: str = "cloudmask.deeplabv3_resnet50_coco"
    weather_image_model_id: str = "restormer.real_denoising"
    weather_video_model_id: str = "rvrt.video_denoising_davis"

    # Identification
    strict_norad_mode: bool = True
    require_norad_for_marking: bool = True
    max_radec_roundtrip_px: float = 2.5
    max_known_tle_age_days: int = 7
    require_observer_for_known: bool = True

    # Observer
    observer_lat: float = 0.0
    observer_lon: float = 0.0
    observer_alt_m: float = 0.0

    # TLE
    tle_active_path: str = "./data/tle_active.txt"
    tle_historical_path: str = ""

    # Output
    output_dir: str = "./outputs"

    def to_dict(self) -> dict:
        return asdict(self)


def load_config() -> Config:
    load_dotenv()
    return Config(
        mode=os.getenv("MODE", "realtime"),
        source_type=os.getenv("SOURCE_TYPE", "directory"),
        source_path=os.getenv("SOURCE_PATH", "./data"),
        asta_model_path=os.getenv("ASTA_MODEL_PATH", "./models/model-best.h5"),
        detection_threshold=float(os.getenv("DETECTION_THRESHOLD", "0.35")),
        max_queue_size=int(os.getenv("MAX_QUEUE_SIZE", "128")),
        sample_every_n=int(os.getenv("SAMPLE_EVERY_N", "1")),
        weather_mode=os.getenv("WEATHER_MODE", "classical"),
        weather_quality_threshold=float(os.getenv("WEATHER_QUALITY_THRESHOLD", "0.16")),
        weather_cloud_cov_threshold=float(os.getenv("WEATHER_CLOUD_COV_THRESHOLD", "0.80")),
        weather_skip_bad_frames=_to_bool(os.getenv("WEATHER_SKIP_BAD_FRAMES"), True),
        weather_cloud_model_id=os.getenv(
            "WEATHER_CLOUD_MODEL_ID", "cloudmask.deeplabv3_resnet50_coco"
        ),
        weather_image_model_id=os.getenv(
            "WEATHER_IMAGE_MODEL_ID", "restormer.real_denoising"
        ),
        weather_video_model_id=os.getenv(
            "WEATHER_VIDEO_MODEL_ID", "rvrt.video_denoising_davis"
        ),
        strict_norad_mode=_to_bool(os.getenv("STRICT_NORAD_MODE"), True),
        require_norad_for_marking=_to_bool(os.getenv("REQUIRE_NORAD_FOR_MARKING"), True),
        max_radec_roundtrip_px=float(os.getenv("MAX_RADEC_ROUNDTRIP_PX", "2.5")),
        max_known_tle_age_days=int(os.getenv("MAX_KNOWN_TLE_AGE_DAYS", "7")),
        require_observer_for_known=_to_bool(os.getenv("REQUIRE_OBSERVER_FOR_KNOWN"), True),
        observer_lat=float(os.getenv("OBSERVER_LAT", "0.0")),
        observer_lon=float(os.getenv("OBSERVER_LON", "0.0")),
        observer_alt_m=float(os.getenv("OBSERVER_ALT_M", "0.0")),
        tle_active_path=os.getenv("TLE_ACTIVE_PATH", "./data/tle_active.txt"),
        tle_historical_path=os.getenv("TLE_HISTORICAL_PATH", ""),
        output_dir=os.getenv("OUTPUT_DIR", "./outputs"),
    )
