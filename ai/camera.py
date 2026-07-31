from __future__ import annotations

from typing import Optional, Tuple, Any


class CameraSource:
    """OpenCV camera/video wrapper.

    source examples:
    - 0 = default laptop/USB webcam
    - 1 = second camera
    - "data/sample_videos/test.mp4" = video file
    """

    def __init__(self, source: int | str = 0):
        self.source = source
        self.cap = None

    def start(self) -> None:
        import cv2
        self.cap = cv2.VideoCapture(self.source)
        if not self.cap.isOpened():
            raise RuntimeError(f"Could not open camera/video source: {self.source}")

    def read(self) -> Tuple[bool, Optional[Any]]:
        if self.cap is None:
            return False, None
        ret, frame = self.cap.read()
        return bool(ret), frame if ret else None

    def release(self) -> None:
        if self.cap is not None:
            self.cap.release()
        self.cap = None
