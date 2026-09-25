"""DEPRECATED: part of the early ai/pipeline.py scaffold, never wired into app.py.

pixel_to_court() below is an identity passthrough placeholder. Real,
calibrated homography is ai/engine/pickle_tracker.py's CourtMapper, fed live
court-corner calibration by ai/tracker_service.py. Kept only for reference.
"""
from __future__ import annotations

from typing import Tuple


def pixel_to_court(x_px: float, y_px: float) -> Tuple[float, float]:
    """Placeholder coordinate mapper.

    Later this will use OpenCV homography from selected court calibration points:
    image pixels -> real pickleball court coordinates.
    """
    # Placeholder only: do not treat this as real measurement.
    return float(x_px), float(y_px)
