"""Background camera + ball-tracking service for the Live Session page.

One daemon thread owns the camera and the YOLO model. It runs the
picklevision_Draft PickleVisionTracker on every frame, JPEG-encodes the
annotated result once, and publishes it. Flask request threads only read the
latest JPEG, so a slow frame never blocks page loads or API calls.

Ball events (bounces + line calls) are produced by the tracker (tracker.events)
and drained by Flask request threads via pop_new_ball_events() -- see
app.py's ingest_live_tracker_events(), called from before_request. Draining
happens on the request thread, not here, so this module never touches Flask's
session/request context.
"""
from __future__ import annotations

import os

# Must be set before any cv2.VideoCapture call (Windows USB camera open delay).
os.environ.setdefault("OPENCV_VIDEOIO_MSMF_ENABLE_HW_TRANSFORMS", "0")

import logging
import threading
import time
from pathlib import Path
from typing import Any, Dict, Iterator, Optional

import cv2

from . import config

log = logging.getLogger("picklevision.tracker")

_STOPPED_STATES = {"idle", "stopped", "error"}
_MAX_BUFFERED_EVENTS = 2000  # tracker.events is not consumed until Milestone 2


def _parse_source(raw: str) -> int | str:
    raw = str(raw).strip()
    return int(raw) if raw.isdigit() else raw


def _load_court_corners() -> Optional[str]:
    """Env var first, then the file written by `pickle_tracker --calibrate`."""
    if config.TRACKER_COURT_CORNERS:
        return config.TRACKER_COURT_CORNERS
    path = Path(config.TRACKER_COURT_CORNERS_FILE)
    if path.exists():
        text = path.read_text(encoding="utf-8").strip()
        return text or None
    return None


class TrackerService:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._new_frame = threading.Condition(self._lock)
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._tracker = None  # PickleVisionTracker; built once, model load is slow
        self._jpeg: Optional[bytes] = None
        self._frame_id = 0
        self._events_cursor = 0  # index into tracker.events already drained by pop_new_ball_events()
        self._status: Dict[str, Any] = {
            "state": "idle",
            "error": None,
            "source": config.TRACKER_SOURCE,
            "device": None,
            "model": str(config.MODEL_PATH),
            "resolution": None,
            "fps": 0.0,
            "inference_ms": 0.0,
            "frames": 0,
            "calibrated": False,
            "tracking": False,
            "debug": None,
        }

    # ------------------------------------------------------------------ public
    def start(self) -> None:
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                return
            self._stop_event.clear()
            self._jpeg = None
            self._events_cursor = 0
            self._status.update(state="starting", error=None, fps=0.0, inference_ms=0.0, frames=0)
            self._thread = threading.Thread(target=self._run, name="picklevision-tracker", daemon=True)
            self._thread.start()

    def stop(self, timeout: float = 5.0) -> None:
        self._stop_event.set()
        thread = self._thread
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=timeout)

    def status(self) -> Dict[str, Any]:
        with self._lock:
            return dict(self._status)

    def live_trajectory(self) -> list[Dict[str, Any]]:
        """The ball's current in-progress path (court feet), for a fast-polled
        live court-map trail -- distinct from pop_new_ball_events(), which only
        returns committed bounce events. Empty when idle or no active lock."""
        with self._lock:
            if self._tracker is None:
                return []
            points = [self._tracker.pixel_to_court_ft(p) for p in self._tracker.primary_trajectory]
        return [{"x": round(x, 3), "y": round(y, 3)} for x, y in points]

    def pop_new_ball_events(self) -> list[Dict[str, Any]]:
        """Drain BallEvents appended since the last call, as plain dicts.

        Called from Flask request threads (see app.py's
        ingest_live_tracker_events()), never from the tracker thread itself --
        keeps DB/session code entirely off the background thread. Locked
        together with the run loop's own trim of tracker.events so the cursor
        stays valid across a trim (see _run).
        """
        with self._lock:
            if self._tracker is None:
                return []
            events = self._tracker.events
            new_events = events[self._events_cursor:]
            self._events_cursor = len(events)
            return [self._event_to_dict(e) for e in new_events]

    def _event_to_dict(self, e: Any) -> Dict[str, Any]:
        return {
            "frame_index": e.frame_index,
            "track_id": e.track_id,
            "centroid": e.centroid,
            "velocity": e.velocity,
            # (x_ft, y_ft) in CourtMapper's convention (x=width, y=length) --
            # BallEvent.landing_point itself is detection-frame pixels, not
            # court feet, so this maps it through the calibrated homography.
            "landing_point_ft": self._tracker.pixel_to_court_ft(e.landing_point),
            "line_call": e.line_call,
            "confidence": e.confidence,
            "timestamp": e.timestamp,
            "camera_id": e.camera_id,
        }

    def mjpeg_stream(self) -> Iterator[bytes]:
        """multipart/x-mixed-replace generator. Each client gets the newest frame;
        slow clients skip frames instead of building a backlog."""
        last_id = -1
        while True:
            with self._new_frame:
                self._new_frame.wait_for(
                    lambda: self._frame_id != last_id or self._status["state"] in _STOPPED_STATES,
                    timeout=1.0,
                )
                if self._status["state"] in _STOPPED_STATES:
                    return
                if self._jpeg is None or self._frame_id == last_id:
                    continue  # still loading the model / opening the camera
                jpeg, last_id = self._jpeg, self._frame_id
            yield (
                b"--frame\r\nContent-Type: image/jpeg\r\nContent-Length: "
                + str(len(jpeg)).encode()
                + b"\r\n\r\n"
                + jpeg
                + b"\r\n"
            )

    # ----------------------------------------------------------------- helpers
    def _set_status(self, **fields: Any) -> None:
        with self._lock:
            self._status.update(fields)
            self._new_frame.notify_all()

    def _build_tracker(self):
        from .engine.pickle_tracker import CourtMapper, PickleVisionTracker

        use_roboflow = config.TRACKER_ROBOFLOW_LOCAL or config.TRACKER_USE_ROBOFLOW
        if not use_roboflow:
            model_path = Path(config.MODEL_PATH)
            # A bare filename with no directory (e.g. "yolov8n.pt") names a stock
            # Ultralytics model that YOLO() auto-downloads on first use; only a
            # path we manage ourselves (models/best.pt) needs to already exist.
            if len(model_path.parts) > 1 and not model_path.exists():
                raise FileNotFoundError(
                    f"Model weights not found at {config.MODEL_PATH}. Copy the v2 best.pt there "
                    "or set PICKLEVISION_MODEL_PATH."
                )

        court_mapper = None
        corners = _load_court_corners()
        if corners:
            court_mapper = CourtMapper(
                src_points=CourtMapper.parse_corners(corners),
                court_width=config.COURT_WIDTH_FT,
                court_length=config.TRACKER_COURT_LENGTH_FT,
            )

        class_id = config.TRACKER_TARGET_CLASS_ID
        tracker = PickleVisionTracker(
            model_name=str(config.MODEL_PATH),
            conf=config.CONFIDENCE_THRESHOLD,
            imgsz=config.TRACKER_IMGSZ,
            device=config.TRACKER_DEVICE,
            target_class_id=None if class_id < 0 else class_id,
            court_mapper=court_mapper,
            target_fps=config.TRACKER_FPS,
            target_width=config.TRACKER_WIDTH,
            target_height=config.TRACKER_HEIGHT,
            zoom_to_court=config.TRACKER_ZOOM,
            exclude_people=config.TRACKER_EXCLUDE_PEOPLE,
            use_roboflow=config.TRACKER_USE_ROBOFLOW,
            roboflow_local=config.TRACKER_ROBOFLOW_LOCAL,
            roboflow_api_url=config.TRACKER_ROBOFLOW_API_URL,
            roboflow_api_key=config.TRACKER_ROBOFLOW_API_KEY,
            roboflow_workspace_name=config.TRACKER_ROBOFLOW_WORKSPACE_NAME,
            roboflow_model_id=config.TRACKER_ROBOFLOW_MODEL_ID,
            roboflow_workflow_id=config.TRACKER_ROBOFLOW_WORKFLOW_ID,
            roboflow_infer_size=config.TRACKER_ROBOFLOW_INFER_SIZE,
        )
        return tracker, court_mapper is not None

    def _debug_snapshot(self) -> Dict[str, Any]:
        """Detection-health counters for /api/camera/status -- answers "is the
        model seeing anything at all?" without needing console access."""
        t = self._tracker
        top_classes = sorted(t.debug_class_counts.items(), key=lambda kv: -kv[1])[:5]
        return {
            "frames_processed": t.debug_frames,
            "target_class_frames": t.debug_target_class_frames,
            "locked_frames": t.debug_locked_frames,
            "top_detected_classes": top_classes,  # [(class_id, frame_count), ...]
        }

    def _reset_track_state(self) -> None:
        """Forget the previous run's ball lock so a restart doesn't draw a stale trail."""
        t = self._tracker
        t.primary_track_id = None
        t.primary_trajectory = []
        t.missed_frames = 0
        t.track_history.clear()
        with self._lock:
            t.events.clear()
            self._events_cursor = 0

    @staticmethod
    def _open_capture(source: int | str):
        from .engine.pickle_tracker import _open_camera

        cap = _open_camera(source)
        if not cap.isOpened():
            raise RuntimeError(
                f"Could not open camera/video source {source!r}. Close other apps using the "
                "camera (including the standalone tracker script) or try another index."
            )
        if isinstance(source, int):
            # Same USB settings as picklevision_Draft's run_video(): MJPEG is what
            # lets the ELP camera reach high fps over USB 2.0.
            cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, config.TRACKER_WIDTH)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, config.TRACKER_HEIGHT)
            cap.set(cv2.CAP_PROP_FPS, config.TRACKER_FPS)
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        return cap

    @staticmethod
    def _encode(frame, fps: float, infer_ms: float) -> Optional[bytes]:
        h, w = frame.shape[:2]
        if w > config.STREAM_MAX_WIDTH:
            new_h = int(h * config.STREAM_MAX_WIDTH / w)
            frame = cv2.resize(frame, (config.STREAM_MAX_WIDTH, new_h), interpolation=cv2.INTER_AREA)
        cv2.putText(
            frame,
            f"{fps:5.1f} fps | {infer_ms:5.1f} ms",
            (10, frame.shape[0] - 12),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            (255, 255, 255),
            2,
        )
        ok, buf = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), config.STREAM_JPEG_QUALITY])
        return buf.tobytes() if ok else None

    # ------------------------------------------------------------- worker loop
    def _run(self) -> None:
        cap = None
        try:
            if self._tracker is None:
                self._set_status(state="loading_model")
                self._tracker, calibrated = self._build_tracker()
                self._set_status(device=str(self._tracker.device), calibrated=calibrated)
            else:
                self._reset_track_state()

            source = _parse_source(config.TRACKER_SOURCE)
            is_file = not isinstance(source, int)
            self._set_status(state="opening_camera", source=str(source))
            cap = self._open_capture(source)

            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            src_fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
            frame_interval = (1.0 / src_fps) if is_file else 0.0  # pace files to real time
            self._set_status(state="running", resolution=f"{width}x{height}")
            log.info("Tracker running on %s, source=%s, %sx%s", self._tracker.device, source, width, height)

            fps_ema = 0.0
            last_tick = time.perf_counter()
            frames = 0

            while not self._stop_event.is_set():
                loop_start = time.perf_counter()
                ok, frame = cap.read()
                if not ok:
                    if is_file and config.TRACKER_LOOP_VIDEO:
                        cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                        self._reset_track_state()
                        continue
                    if is_file:
                        break  # end of video -> "stopped"
                    raise RuntimeError("Camera stopped delivering frames (unplugged or in use?).")

                t0 = time.perf_counter()
                annotated = self._tracker.process_frame(frame)
                infer_ms = (time.perf_counter() - t0) * 1000.0

                now = time.perf_counter()
                inst_fps = 1.0 / max(now - last_tick, 1e-6)
                last_tick = now
                fps_ema = inst_fps if fps_ema == 0.0 else 0.9 * fps_ema + 0.1 * inst_fps
                frames += 1

                jpeg = self._encode(annotated, fps_ema, infer_ms)
                if jpeg is not None:
                    with self._lock:
                        # Trim under the same lock pop_new_ball_events() reads under,
                        # so shrinking the list can't invalidate its cursor mid-read.
                        if len(self._tracker.events) > _MAX_BUFFERED_EVENTS:
                            cut = len(self._tracker.events) - (_MAX_BUFFERED_EVENTS // 4)
                            del self._tracker.events[:cut]
                            self._events_cursor = max(0, self._events_cursor - cut)
                        self._jpeg = jpeg
                        self._frame_id += 1
                        self._status.update(
                            fps=round(fps_ema, 1),
                            inference_ms=round(infer_ms, 1),
                            frames=frames,
                            tracking=self._tracker.primary_track_id is not None,
                            debug=self._debug_snapshot(),
                        )
                        self._new_frame.notify_all()

                if frame_interval:
                    remaining = frame_interval - (time.perf_counter() - loop_start)
                    if remaining > 0:
                        self._stop_event.wait(remaining)
        except Exception as exc:  # surfaced in the UI via /api/camera/status
            log.exception("Tracker service failed")
            self._set_status(state="error", error=str(exc))
        finally:
            if cap is not None:
                cap.release()
            with self._lock:
                if self._status["state"] != "error":
                    self._status["state"] = "stopped"
                self._new_frame.notify_all()


tracker_service = TrackerService()
