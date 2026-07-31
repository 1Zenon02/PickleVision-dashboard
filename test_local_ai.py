from __future__ import annotations

import sys
from pathlib import Path

import cv2

from ai.config import MODEL_PATH, TEST_RESULTS_DIR
from ai.detector import detect_balls, get_model_status


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage:")
        print("  py test_local_ai.py path/to/test_image.jpg")
        print()
        print("Before running, put your trained YOLO model here:")
        print(f"  {MODEL_PATH}")
        return 1

    image_path = Path(sys.argv[1])
    if not image_path.exists():
        print(f"Image not found: {image_path}")
        return 1

    status = get_model_status()
    if not status["available"]:
        print("Local AI model is not ready yet.")
        print(f"Put best.pt here: {MODEL_PATH}")
        return 1

    frame = cv2.imread(str(image_path))
    if frame is None:
        print(f"Could not read image: {image_path}")
        return 1

    detections = detect_balls(frame)
    print(f"Detections found: {len(detections)}")
    for i, det in enumerate(detections, start=1):
        print(f"{i}. center=({det['ball_x']}, {det['ball_y']}), confidence={det['confidence']}")

    output = frame.copy()
    for det in detections:
        x1, y1, x2, y2 = int(det["x1"]), int(det["y1"]), int(det["x2"]), int(det["y2"])
        cv2.rectangle(output, (x1, y1), (x2, y2), (0, 255, 0), 2)
        cv2.putText(
            output,
            f"pickleball {det['confidence']:.2f}",
            (x1, max(20, y1 - 8)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (0, 255, 0),
            2,
        )

    TEST_RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = TEST_RESULTS_DIR / f"detected_{image_path.name}"
    cv2.imwrite(str(out_path), output)
    print(f"Saved result image: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
