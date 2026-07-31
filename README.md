# Project PickleVision Dashboard v2

This is a hardware-ready prototype dashboard for Project PickleVision. It runs using simulated ball events first so the dashboard, reports, event logging, and export functions can be tested before the camera and Raspberry Pi are available.

## What is improved

- Live IN/OUT call display
- Confidence score
- Bounce X/Y coordinates
- Full visible rally trajectory drawing from recent ball-tracking points
- Latency and FPS metrics
- CPU/RAM usage display
- Event log table
- Reports page with accuracy, precision, recall, F1-score, MAE, and confusion matrix
- Heatmap-style bounce distribution
- CSV export
- Calibration checklist page
- Local SQLite database storage

## How to run

```bash
cd picklevision_dashboard_v2
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

Then open:

```text
http://127.0.0.1:5000
```


## Connecting real AI data to the dashboard

This version now includes a bridge API for the future AI/camera code:

```text
POST /api/update-live-data
```

Send JSON like this from the camera, Raspberry Pi, or local AI script:

```json
{
  "system_call": "IN",
  "confidence": 0.91,
  "bounce_x": 18.5,
  "bounce_y": 7.2,
  "latency_ms": 42.1,
  "fps": 24.8,
  "trajectory": [
    {"x": 12.0, "y": 8.0},
    {"x": 18.5, "y": 7.2}
  ]
}
```

The dashboard will save it to SQLite and show it in the live dashboard, reports, history, and CSV export.

You can test the bridge using:

```powershell
py send_sample_event.py
```

For optional protection, start Flask with an API key:

```powershell
set PICKLEVISION_API_KEY=your-secret-key
py app.py
```

Then the sender must include the same key using the `X-PickleVision-Key` header.

To check model and dashboard status, open:

```text
http://127.0.0.1:5000/api/ai-status
```


## Visible rally tracking on the court map

The court map now draws a longer visible rally path instead of only one short line.

- `trajectory` should contain frame-by-frame court points in feet, for example `{"x": 12.0, "y": 8.0}`.
- The dashboard combines the latest events into `rally_trajectory`, so viewers can see where the ball came from and where it bounced.
- The map labels the start of the visible path and the latest bounce/call.
- `ai/pipeline.py` now converts tracked pixel points into court coordinates before sending them to the dashboard.

## Development stages

1. **Simulation mode** - current mode. Uses fake events so the dashboard can be tested.
2. **Recorded video mode** - next step. Replace simulated events with processed sample videos.
3. **Webcam mode** - test with a laptop/USB camera.
4. **Raspberry Pi / edge mode** - replace the input module with the final camera and model pipeline.

## Where to connect the future model

The current function is:

```python
simulate_event()
```

Later, replace its output with real values from the camera/model pipeline:

- system_call
- confidence
- bounce_x
- bounce_y
- latency_ms
- fps
- trajectory
- human_call, if doing validation
- error_distance_mm, if comparing to annotated ground truth

The dashboard will continue working as long as the API returns the same JSON structure.

## Doubles pickleball scoring added

The live dashboard now includes a doubles side-out scoring panel.

Prototype scoring behavior requested for the dashboard:

- Before the game starts, the display shows `0-0-0`
- Pressing `Start Game` changes the live score call to `0-0-1`
- Score format: serving team score - receiving team score - server number
- The dashboard shows the current serving team, current server/player name, receiving team, latest rally winner, and latest scorer
- Only the serving team can score a point in side-out scoring
- If the serving team loses with Server 1, the serve moves to Server 2
- If the serving team loses with Server 2, a side-out happens and the other team serves
- Normal target score is 11, win by 2

Important note: official side-out doubles scoring normally starts at `0-0-2`. This prototype was adjusted to the requested display of `0-0-0` before start and `0-0-1` after pressing Start Game.

Dashboard buttons:

- `Start Game` - starts the live score call at `0-0-1`
- `Serving Team Won Rally` - adds a point to the serving team and records the scorer/server
- `Receiving Team Won Rally` - records the rally winner, then moves the serve to Server 2 or causes side-out
- `Reset Score` - resets the display back to `0-0-0`

Scoring API routes:

```text
GET  /api/score
POST /api/score/start
POST /api/score/reset
POST /api/score/rally
```

Example rally update:

```json
{
  "winner": "serving"
}
```

or

```json
{
  "winner": "receiving"
}
```

## Latest dashboard cleanup

This version removes extra helper text from the landing and sign-up screens. The live dashboard now connects doubles scoring to the court map by showing the current server, serving side, receiver marker, and diagonal service guide line.

The court map now draws only the latest rally/shot trajectory instead of combining many old simulated paths. This makes the ball path easier to read while still allowing the real AI pipeline to send a full trajectory list through `/api/update-live-data`.

## Role-based dashboards

The sign-up form now asks the user to choose either Player or Coach.

Player flow:

```text
Player login -> Player Dashboard
```

The Player Dashboard includes these tabs:

- My Matches
- My Statistics
- My Trajectory
- My Reports

Coach flow:

```text
Coach login -> Coach Dashboard
```

The Coach Dashboard includes these tabs:

- Player List
- Selected Player Stats
- Match Review
- Trajectory Review
- Reports

The route `/dashboard` now works as the role gateway. It automatically sends player accounts to `/player-dashboard` and coach accounts to `/coach-dashboard`. The original real-time game view is still available at `/live-dashboard`.
