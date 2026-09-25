"""DEPRECATED: part of the early ai/pipeline.py scaffold, never wired into app.py.

Do not confuse with ai/engine/pickle_tracker.py (PickleVisionTracker), the
real, active tracker run by ai/tracker_service.py. Kept only for reference.
"""
from __future__ import annotations

from typing import Dict, List


class BallTracker:
    """Stores recent ball coordinates to create a trajectory."""

    def __init__(self, max_points: int = 30):
        self.max_points = max_points
        self.points: List[Dict[str, float]] = []

    def update(self, x: float, y: float) -> List[Dict[str, float]]:
        self.points.append({"x": round(x, 2), "y": round(y, 2)})
        self.points = self.points[-self.max_points:]
        return self.points

    def reset(self) -> None:
        self.points.clear()
