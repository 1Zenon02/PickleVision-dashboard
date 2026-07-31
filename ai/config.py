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

# Place your Roboflow/YOLO trained model here:
MODEL_PATH = Path(os.environ.get("PICKLEVISION_MODEL_PATH", MODELS_DIR / "best.pt"))

# Detection confidence threshold. Increase if it detects wrong objects; lower if it misses the ball.
CONFIDENCE_THRESHOLD = float(os.environ.get("PICKLEVISION_CONF", "0.25"))

# Dashboard event schema expected by app.py
REQUIRED_EVENT_KEYS = [
    "session_id", "timestamp", "system_call", "human_call", "confidence",
    "bounce_x", "bounce_y", "court_zone", "latency_ms", "fps",
    "error_distance_mm", "correct", "trajectory",
]
