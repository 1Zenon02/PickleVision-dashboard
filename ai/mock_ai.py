from __future__ import annotations

import math
import random
from datetime import datetime
from typing import Any, Dict, List

from .config import COURT_LENGTH_FT, COURT_WIDTH_FT
from .line_caller import classify_bounce, court_zone


def generate_trajectory(bounce_x: float, bounce_y: float) -> List[Dict[str, float]]:
    """Create a fake full-rally trajectory ending near the simulated bounce point."""
    # Start from the opposite half of the court so the dashboard trail shows
    # where the ball came from, not only the final bounce.
    if bounce_x > COURT_LENGTH_FT / 2:
        start_x = random.uniform(2.0, 12.0)
    else:
        start_x = random.uniform(COURT_LENGTH_FT - 12.0, COURT_LENGTH_FT - 2.0)
    start_y = random.uniform(2.0, COURT_WIDTH_FT - 2.0)

    points: List[Dict[str, float]] = []
    total_points = 18
    for i in range(total_points):
        t = i / (total_points - 1)
        curve = math.sin(t * math.pi) * random.uniform(1.8, 4.2)
        wiggle = math.sin(t * math.pi * 3) * random.uniform(0.2, 0.7)
        points.append({
            "x": round(start_x + (bounce_x - start_x) * t, 2),
            "y": round(start_y + (bounce_y - start_y) * t + curve + wiggle, 2),
        })
    return points


def generate_mock_event(session_id: str) -> Dict[str, Any]:
    """Generate one fake AI output event for dashboard testing.

    This function is the temporary replacement for the future real AI pipeline.
    The returned dictionary is the contract between the AI code and dashboard.
    """
    x = random.uniform(-1.5, COURT_LENGTH_FT + 1.5)
    y = random.uniform(-1.2, COURT_WIDTH_FT + 1.2)

    system_call = classify_bounce(x, y)

    # Simulate a human validation call so reports can compute accuracy/F1.
    human_call = system_call if random.random() > 0.12 else ("OUT" if system_call == "IN" else "IN")
    correct = 1 if human_call == system_call else 0

    confidence = random.uniform(0.78, 0.98) if correct else random.uniform(0.52, 0.77)
    latency = random.uniform(28, 78)
    fps = random.uniform(18, 31)
    error_distance_mm = random.uniform(8, 35) if correct else random.uniform(45, 120)

    clamped_x = max(0, min(COURT_LENGTH_FT, x))
    clamped_y = max(0, min(COURT_WIDTH_FT, y))

    return {
        "session_id": session_id,
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "system_call": system_call,
        "human_call": human_call,
        "confidence": round(confidence, 3),
        "bounce_x": round(x, 2),
        "bounce_y": round(y, 2),
        "court_zone": court_zone(x, y),
        "latency_ms": round(latency, 1),
        "fps": round(fps, 1),
        "error_distance_mm": round(error_distance_mm, 1),
        "correct": correct,
        "trajectory": generate_trajectory(clamped_x, clamped_y),
    }
