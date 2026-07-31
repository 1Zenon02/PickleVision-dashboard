from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from .config import CONFIDENCE_THRESHOLD, MODEL_PATH

_model = None
_model_error: Optional[str] = None


def model_is_available() -> bool:
    """Return True when models/best.pt exists."""
    return Path(MODEL_PATH).exists()


def load_model():
    """Load the local YOLO model once.

    Put your Roboflow/YOLO trained model at:
        models/best.pt
    """
    global _model, _model_error

    if _model is not None:
        return _model

    if not model_is_available():
        _model_error = f"Model not found: {MODEL_PATH}"
        return None

    try:
        from ultralytics import YOLO
        _model = YOLO(str(MODEL_PATH))
        _model_error = None
        return _model
    except Exception as exc:  # pragma: no cover
        _model_error = str(exc)
        return None


def get_model_status() -> Dict[str, Any]:
    return {
        "available": model_is_available(),
        "path": str(MODEL_PATH),
        "loaded": _model is not None,
        "error": _model_error,
    }


def detect_ball(frame: Any, conf: float = CONFIDENCE_THRESHOLD) -> Optional[Dict[str, float]]:
    """Detect the pickleball from a frame/image using local YOLO.

    Input can be:
    - OpenCV frame / numpy array
    - image path string

    Output format expected by the rest of the AI pipeline:
        {"ball_x": 520.0, "ball_y": 310.0, "confidence": 0.91}
    """
    detections = detect_balls(frame, conf=conf)
    if not detections:
        return None
    # Use the highest-confidence detection as the ball.
    return max(detections, key=lambda d: d["confidence"])


def detect_balls(frame: Any, conf: float = CONFIDENCE_THRESHOLD) -> List[Dict[str, float]]:
    model = load_model()
    if model is None:
        return []

    results = model.predict(source=frame, conf=conf, verbose=False)
    detections: List[Dict[str, float]] = []

    for result in results:
        boxes = getattr(result, "boxes", None)
        if boxes is None:
            continue

        for box in boxes:
            x1, y1, x2, y2 = box.xyxy[0].tolist()
            confidence = float(box.conf[0])
            class_id = int(box.cls[0]) if box.cls is not None else 0

            center_x = (float(x1) + float(x2)) / 2.0
            center_y = (float(y1) + float(y2)) / 2.0

            detections.append(
                {
                    "ball_x": round(center_x, 2),
                    "ball_y": round(center_y, 2),
                    "confidence": round(confidence, 4),
                    "x1": round(float(x1), 2),
                    "y1": round(float(y1), 2),
                    "x2": round(float(x2), 2),
                    "y2": round(float(y2), 2),
                    "class_id": class_id,
                }
            )

    return detections
