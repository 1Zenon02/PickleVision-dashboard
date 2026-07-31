"""Send one sample AI event to the PickleVision dashboard.

Run the Flask app first:
    py app.py

Then in another terminal:
    py send_sample_event.py
"""

from __future__ import annotations

import json
import math
import random
import urllib.request
from datetime import datetime

URL = "http://127.0.0.1:5000/api/update-live-data"


def make_sample_trajectory() -> list[dict[str, float]]:
    start_x = random.uniform(4, 10)
    start_y = random.uniform(3, 17)
    end_x = random.uniform(16, 42)
    end_y = random.uniform(3, 17)
    points = []
    for i in range(22):
        t = i / 21
        arc = math.sin(t * math.pi) * 3.0
        points.append({
            "x": round(start_x + (end_x - start_x) * t, 2),
            "y": round(start_y + (end_y - start_y) * t + arc, 2),
        })
    return points


trajectory = make_sample_trajectory()
bounce = trajectory[-1]
payload = {
    "timestamp": datetime.now().isoformat(timespec="seconds"),
    "system_call": "IN" if 0 <= bounce["x"] <= 44 and 0 <= bounce["y"] <= 20 else "OUT",
    "confidence": round(random.uniform(0.82, 0.96), 3),
    "bounce_x": bounce["x"],
    "bounce_y": bounce["y"],
    "latency_ms": round(random.uniform(30, 70), 1),
    "fps": round(random.uniform(20, 32), 1),
    "trajectory": trajectory,
}

request = urllib.request.Request(
    URL,
    data=json.dumps(payload).encode("utf-8"),
    headers={"Content-Type": "application/json"},
    method="POST",
)

with urllib.request.urlopen(request, timeout=10) as response:
    print(response.read().decode("utf-8"))
