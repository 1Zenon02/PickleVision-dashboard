from __future__ import annotations

from pathlib import Path
import os

BASE_DIR = Path(__file__).resolve().parent.parent

# Loads .env (gitignored) so secrets like PICKLEVISION_ROBOFLOW_API_KEY survive
# across terminal sessions instead of needing `$env:` set every new tab. Copy
# .env.example to .env and fill in real values; missing file/package is fine.
try:
    from dotenv import load_dotenv

    load_dotenv(BASE_DIR / ".env")
except ImportError:
    pass
MODELS_DIR = BASE_DIR / "models"
DATA_DIR = BASE_DIR / "data"
TEST_IMAGES_DIR = DATA_DIR / "test_images"
TEST_RESULTS_DIR = DATA_DIR / "test_results"

COURT_LENGTH_FT = 44.0
COURT_WIDTH_FT = 20.0

# Change to "local_model" later when best.pt is available and you want app.py to use real detections.
AI_MODE = os.environ.get("PICKLEVISION_AI_MODE", "mock")

# Only used when TRACKER_ROBOFLOW_LOCAL/TRACKER_USE_ROBOFLOW are both off. Until
# a local best.pt exists, fall back to the stock COCO yolov8n.pt (auto-downloaded
# by ultralytics) so the camera pipeline is still testable -- it detects COCO's
# generic "sports ball" class (id 32, see TRACKER_TARGET_CLASS_ID below), not a
# pickleball specifically.
_DEFAULT_MODEL_PATH = MODELS_DIR / "best.pt"
MODEL_PATH = Path(
    os.environ.get(
        "PICKLEVISION_MODEL_PATH",
        _DEFAULT_MODEL_PATH if _DEFAULT_MODEL_PATH.exists() else "yolov8n.pt",
    )
)

# Detection confidence threshold. Increase if it detects wrong objects; lower if it misses the ball.
CONFIDENCE_THRESHOLD = float(os.environ.get("PICKLEVISION_CONF", "0.25"))

# ---- Roboflow-hosted model (alternative to a local best.pt) ---------------
# The actual trained ball model lives on Roboflow, not as a file you copy in.
# roboflow_local runs it in-process via the `inference` package: weights
# download once with the API key, then cache offline (see MODEL_CACHE_DIR in
# pickle_tracker.py). Only PICKLEVISION_ROBOFLOW_MODEL_ID (e.g.
# "project-slug/3") and PICKLEVISION_ROBOFLOW_API_KEY are required to turn
# this on; everything else stays on the local-.pt path above until both are set.
TRACKER_ROBOFLOW_MODEL_ID = os.environ.get("PICKLEVISION_ROBOFLOW_MODEL_ID") or None
TRACKER_ROBOFLOW_API_KEY = os.environ.get("PICKLEVISION_ROBOFLOW_API_KEY") or None
TRACKER_ROBOFLOW_WORKSPACE_NAME = os.environ.get("PICKLEVISION_ROBOFLOW_WORKSPACE_NAME") or None
# Workflows aren't supported by roboflow_local (model-id only); this is only
# used when TRACKER_USE_ROBOFLOW (the self-hosted HTTP server path) is on.
TRACKER_ROBOFLOW_WORKFLOW_ID = os.environ.get("PICKLEVISION_ROBOFLOW_WORKFLOW_ID") or None
TRACKER_ROBOFLOW_API_URL = os.environ.get("PICKLEVISION_ROBOFLOW_API_URL", "http://localhost:9001")
TRACKER_ROBOFLOW_INFER_SIZE = int(os.environ.get("PICKLEVISION_ROBOFLOW_INFER_SIZE", "640"))
# Auto-enables once a model id + API key are configured; set to "0" to force
# the local-.pt path back on even with those present.
TRACKER_ROBOFLOW_LOCAL = os.environ.get(
    "PICKLEVISION_ROBOFLOW_LOCAL",
    "1" if (TRACKER_ROBOFLOW_MODEL_ID and TRACKER_ROBOFLOW_API_KEY) else "0",
) not in ("0", "false", "False")
# Self-hosted Roboflow inference server over HTTP instead of in-process --
# off by default; only used if you're running a Docker inference server.
TRACKER_USE_ROBOFLOW = os.environ.get("PICKLEVISION_ROBOFLOW_SERVER", "0") not in ("0", "false", "False")

# Dashboard event schema expected by app.py
REQUIRED_EVENT_KEYS = [
    "session_id", "timestamp", "system_call", "human_call", "confidence",
    "bounce_x", "bounce_y", "court_zone", "latency_ms", "fps",
    "error_distance_mm", "correct", "trajectory",
]

# ---- Ball-tracking engine (ai/engine/pickle_tracker.py) --------------------
# Video file path, or a USB camera index as a string (e.g. "0"). Index 0 is
# this laptop's built-in/first-enumerated webcam; the external ELP camera
# showed up at index 1 -- change this if your camera order differs.
TRACKER_SOURCE = os.environ.get("PICKLEVISION_TRACKER_SOURCE", "1")
TRACKER_WIDTH = int(os.environ.get("PICKLEVISION_TRACKER_WIDTH", "1920"))
TRACKER_HEIGHT = int(os.environ.get("PICKLEVISION_TRACKER_HEIGHT", "1080"))
TRACKER_FPS = int(os.environ.get("PICKLEVISION_TRACKER_FPS", "120"))
# Higher than the stock 640 default: a pickleball is a small object in a
# 1920x1080 frame, so more inference pixels helps catch it at range. Costs
# some speed -- only worth raising once there's GPU headroom to spare.
TRACKER_IMGSZ = int(os.environ.get("PICKLEVISION_TRACKER_IMGSZ", "960"))
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

# Runs a second yolov8n person-detector every frame to reject ball-colored
# clothing during re-acquisition/prediction -- costs a full extra model pass
# (~10-15ms on GPU). On by default (real match footage has players in frame);
# turn off for close-range/no-player testing, as the picklevision_Draft author
# does with --no-exclude-people.
TRACKER_EXCLUDE_PEOPLE = os.environ.get("PICKLEVISION_TRACKER_EXCLUDE_PEOPLE", "1") not in ("0", "false", "False")

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
