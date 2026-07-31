from __future__ import annotations

from typing import Dict, List, Optional


class BounceDetector:
    """Simple placeholder bounce detector.

    Later this should detect when the ball contacts the court using trajectory
    direction changes, speed changes, and/or model confidence.
    """

    def detect(self, trajectory: List[Dict[str, float]]) -> Optional[Dict[str, float]]:
        if len(trajectory) < 3:
            return None
        # Temporary placeholder: use the latest point as a possible bounce.
        last = trajectory[-1]
        return {"bounce_detected": True, "bounce_x": last["x"], "bounce_y": last["y"]}
