from __future__ import annotations

from pathlib import Path
import os

BASE_DIR = Path(__file__).resolve().parent.parent
MODELS_DIR = BASE_DIR / "models"
DATA_DIR = BASE_DIR / "data"
TEST_IMAGES_DIR = DATA_DIR / "test_images"
TEST_RESULTS_DIR = DATA_DIR / "test_results"

COURT_LENGTH_FT = 44.0
COURT_WIDTH_FT = 20.0

# Change to "local_model" later when best.pt is available and you want app.py to use real detections.
AI_MODE = os.environ.get("PICKLEVISION_AI_MODE", "mock")

# Place your Roboflow/YOLO trained model here. Until it exists, fall back to the
# stock COCO yolov8n.pt (auto-downloaded by ultralytics) so the camera pipeline
# is still testable -- it detects COCO's generic "sports ball" class (id 32,
# see TRACKER_TARGET_CLASS_ID below), not a pickleball specifically.
_DEFAULT_MODEL_PATH = MODELS_DIR / "best.pt"
MODEL_PATH = Path(
    os.environ.get(
        "PICKLEVISION_MODEL_PATH",
        _DEFAULT_MODEL_PATH if _DEFAULT_MODEL_PATH.exists() else "yolov8n.pt",
    )
)

# Detection confidence threshold. Increase if it detects wrong objects; lower if it misses the ball.
CONFIDENCE_THRESHOLD = float(os.environ.get("PICKLEVISION_CONF", "0.25"))

# Dashboard event schema expected by app.py
REQUIRED_EVENT_KEYS = [
    "session_id", "timestamp", "system_call", "human_call", "confidence",
    "bounce_x", "bounce_y", "court_zone", "latency_ms", "fps",
    "error_distance_mm", "correct", "trajectory",
]

# ---- Ball-tracking engine (ai/engine/pickle_tracker.py) --------------------
# Video file path, or a USB camera index as a string (e.g. "0").
TRACKER_SOURCE = os.environ.get("PICKLEVISION_TRACKER_SOURCE", "0")
TRACKER_WIDTH = int(os.environ.get("PICKLEVISION_TRACKER_WIDTH", "1920"))
TRACKER_HEIGHT = int(os.environ.get("PICKLEVISION_TRACKER_HEIGHT", "1080"))
TRACKER_FPS = int(os.environ.get("PICKLEVISION_TRACKER_FPS", "120"))
TRACKER_IMGSZ = int(os.environ.get("PICKLEVISION_TRACKER_IMGSZ", "640"))
# 'cuda', 'cpu', or None to auto-detect GPU.
TRACKER_DEVICE = os.environ.get("PICKLEVISION_TRACKER_DEVICE") or None
# COCO 'sports ball' class id for the stock yolov8n.pt weights; a custom
# single-class model almost always uses class 0. -1 tracks every class.
TRACKER_TARGET_CLASS_ID = int(os.environ.get("PICKLEVISION_TRACKER_TARGET_CLASS_ID", "32"))
# Loop a video-file source back to frame 0 at EOF instead of stopping.
TRACKER_LOOP_VIDEO = os.environ.get("PICKLEVISION_TRACKER_LOOP_VIDEO", "1") not in ("0", "false", "False")
# Digitally crop detection/display to the calibrated court region.
TRACKER_ZOOM = os.environ.get("PICKLEVISION_TRACKER_ZOOM", "0") not in ("0", "false", "False")
TRACKER_COURT_LENGTH_FT = float(os.environ.get("PICKLEVISION_TRACKER_COURT_LENGTH_FT", str(COURT_LENGTH_FT)))

# Calibration: "x1 y1 x2 y2 x3 y3 x4 y4" (TL TR BR BL). Env var wins; otherwise
# tracker_service falls back to TRACKER_COURT_CORNERS_FILE, written by
# `pickle_tracker.py --calibrate --calibration-output <path>`.
TRACKER_COURT_CORNERS = os.environ.get("PICKLEVISION_TRACKER_COURT_CORNERS")
TRACKER_COURT_CORNERS_FILE = Path(
    os.environ.get("PICKLEVISION_TRACKER_COURT_CORNERS_FILE", DATA_DIR / "court_corners.txt")
)

# ---- Live video stream (/video_feed) ----------------------------------
STREAM_MAX_WIDTH = int(os.environ.get("PICKLEVISION_STREAM_MAX_WIDTH", "960"))
STREAM_JPEG_QUALITY = int(os.environ.get("PICKLEVISION_STREAM_JPEG_QUALITY", "80"))
