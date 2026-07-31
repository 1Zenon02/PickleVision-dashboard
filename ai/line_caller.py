from __future__ import annotations

from .config import COURT_LENGTH_FT, COURT_WIDTH_FT


def classify_bounce(x_ft: float, y_ft: float) -> str:
    """Return IN if the mapped bounce coordinate is inside the court rectangle.

    This is the first rule-based line-calling logic. It does not yet include
    kitchen faults, serve rules, or full pickleball rulebook logic.
    """
    if 0 <= x_ft <= COURT_LENGTH_FT and 0 <= y_ft <= COURT_WIDTH_FT:
        return "IN"
    return "OUT"


def court_zone(x_ft: float, y_ft: float) -> str:
    clamped_x = max(0, min(COURT_LENGTH_FT, x_ft))
    clamped_y = max(0, min(COURT_WIDTH_FT, y_ft))
    side = "Left" if clamped_x < COURT_LENGTH_FT / 2 else "Right"
    zone = "Kitchen / NVZ" if 15 <= clamped_x <= 29 else "Back Court"
    lane = "Bottom Lane" if clamped_y < COURT_WIDTH_FT / 2 else "Top Lane"
    return f"{side} {zone} - {lane}"
