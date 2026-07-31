# PickleVision AI Folder Guide

This version adds an `ai/` folder to prepare the project for the future camera/Raspberry Pi setup.

## Current status

The dashboard is still using mock/simulated AI data from:

```python
ai/mock_ai.py
```

`app.py` calls:

```python
generate_mock_event(SESSION_ID)
```

That produces the same event format that the dashboard expects.


## Sending AI output to the dashboard

After your detector/tracker has a bounce result, do not edit the dashboard page directly. Send the result to Flask instead:

```text
POST http://127.0.0.1:5000/api/update-live-data
```

Minimum JSON fields:

```json
{
  "system_call": "OUT",
  "confidence": 0.88,
  "bounce_x": 45.2,
  "bounce_y": 8.1
}
```

Optional fields are `latency_ms`, `fps`, `trajectory`, `human_call`, `error_distance_mm`, and `correct`. For visible rally tracking, send `trajectory` as a list of court-coordinate points in feet, not just the final bounce.
The app will automatically add timestamp, court zone, and other missing values.

## Future real AI flow

When the camera and Raspberry Pi arrive, the goal is to replace the mock event generator with this pipeline:

```text
Camera -> detector.py -> tracker.py -> bounce_detector.py -> homography.py -> line_caller.py -> dashboard

The dashboard expects the final trajectory in court coordinates so it can draw the rally path from the start of the visible ball movement up to the latest bounce.
```

## Files

- `mock_ai.py` - simulation data for the dashboard. Use this now.
- `camera.py` - future camera/video input wrapper.
- `detector.py` - future YOLO/TrackNet/OpenCV ball detector.
- `tracker.py` - stores ball points to form a trajectory.
- `bounce_detector.py` - future bounce/contact detector.
- `homography.py` - future pixel-to-court coordinate conversion.
- `line_caller.py` - rule-based IN/OUT decision after court mapping.
- `pipeline.py` - future real AI pipeline entry point.

## What to edit later

When equipment arrives, do not redesign the dashboard first. Start by filling in:

1. `camera.py` - make sure frames can be read from the camera.
2. `detector.py` - make it return ball coordinates and confidence.
3. `homography.py` - add real court calibration.
4. `pipeline.py` - connect all parts and return the same event dictionary format.

## Local AI test in VS Code

This version can test a Roboflow/YOLO model locally.

### 1. Put the trained model here

```text
models/best.pt
```

Ask your teammate for the Roboflow/YOLO trained model file, usually named `best.pt`.

### 2. Install dependencies

```powershell
py -m pip install -r requirements.txt
```

### 3. Put a test image here

```text
data/test_images/test.jpg
```

### 4. Run local AI test

```powershell
py test_local_ai.py data/test_images/test.jpg
```

The result image will be saved in:

```text
data/test_results/
```

### Current status

The dashboard still uses mock AI for normal dashboard operation. The local AI test script is for checking if the trained model can detect the pickleball locally in VS Code. After this works, the next step is connecting `ai/detector.py` into `ai/pipeline.py` for video/camera mode.
