"""DEPRECATED: early scaffold, never wired into app.py.

The active implementation is ai/engine/pickle_tracker.py (PickleVisionTracker)
run by ai/tracker_service.py -- it already does real detection, physics-based
bounce detection, and homography-based line calling, more capably than the
placeholders this module chains together. Kept only for reference.
"""
from __future__ import annotations

import time
from datetime import datetime
from typing import Any, Dict, Optional

from .bounce_detector import BounceDetector
from .detector import detect_ball
from .homography import pixel_to_court
from .line_caller import classify_bounce, court_zone
from .tracker import BallTracker

tracker = BallTracker()
bounce_detector = BounceDetector()


def process_frame(frame: Any, session_id: str) -> Optional[Dict[str, Any]]:
    """Process one camera/video frame and return a dashboard-ready event.

    Flow:
    camera frame -> detector -> tracker -> bounce detector -> homography -> line caller -> dashboard event.

    The detector only works after a YOLO/Roboflow model is placed in models/best.pt.
    """
    start = time.perf_counter()
    detection = detect_ball(frame)
    if not detection:
        return None

    pixel_trajectory = tracker.update(detection["ball_x"], detection["ball_y"])
    bounce = bounce_detector.detect(pixel_trajectory)
    if not bounce:
        return None

    court_x, court_y = pixel_to_court(bounce["bounce_x"], bounce["bounce_y"])
    system_call = classify_bounce(court_x, court_y)

    # Convert the frame-by-frame track from image pixels into court coordinates
    # so the dashboard can draw the whole rally path on the pickleball court map.
    court_trajectory = []
    for point in pixel_trajectory:
        px = point.get("x", point.get("ball_x", 0)) if isinstance(point, dict) else 0
        py = point.get("y", point.get("ball_y", 0)) if isinstance(point, dict) else 0
        tx, ty = pixel_to_court(px, py)
        court_trajectory.append({"x": tx, "y": ty})

    latency_ms = (time.perf_counter() - start) * 1000.0

    return {
        "session_id": session_id,
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "system_call": system_call,
        "human_call": None,
        "confidence": detection.get("confidence", 0.0),
        "bounce_x": court_x,
        "bounce_y": court_y,
        "court_zone": court_zone(court_x, court_y),
        "latency_ms": round(latency_ms, 2),
        "fps": round(1000.0 / latency_ms, 2) if latency_ms > 0 else 0.0,
        "error_distance_mm": None,
        "correct": None,
        "trajectory": court_trajectory,
    }
