from __future__ import annotations

import csv
import io
import json
import math
import os
import random
import sqlite3
import time
from datetime import datetime
from functools import wraps
from pathlib import Path
from threading import Lock
from typing import Any, Dict, List, Optional

from flask import Flask, Response, flash, jsonify, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from ai.mock_ai import generate_mock_event


from ai.mock_ai import generate_mock_event

# Add Firebase imports here:
import firebase_admin
from firebase_admin import credentials, firestore

try:
    import psutil  # optional, used when available
except Exception:  # pragma: no cover
    psutil = None

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "picklevision.db"
DATA_DIR.mkdir(exist_ok=True)

app = Flask(__name__)
app.secret_key = os.environ.get("PICKLEVISION_SECRET", "picklevision_development_secret")
# Optional protection for AI/Raspberry Pi event posting.
# Set PICKLEVISION_API_KEY in your environment, then send it using the
# X-PickleVision-Key header. If unset, local prototype posting is allowed.

# Initialize Firebase Admin SDK
cred = credentials.Certificate("firebase-key.json")
firebase_admin.initialize_app(cred)
firestore_db = firestore.client()

API_INGEST_KEY = os.environ.get("PICKLEVISION_API_KEY", "").strip()

state_lock = Lock()
SIMULATION_ENABLED = True
SESSION_ID = datetime.now().strftime("S%Y%m%d%H%M%S")
LAST_EVENT_TS = 0.0

COURT_LENGTH_FT = 44.0
COURT_WIDTH_FT = 20.0


def db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, timeout=30, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout = 30000")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def column_exists(conn: sqlite3.Connection, table: str, column: str) -> bool:
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return any(row["name"] == column for row in rows)


def init_db() -> None:
    with db() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                full_name TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'coach',
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS players (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                player_name TEXT NOT NULL,
                team_name TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY(user_id) REFERENCES users(id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS games (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                player_id INTEGER NOT NULL,
                opponent_name TEXT NOT NULL,
                player_score INTEGER NOT NULL DEFAULT 0,
                opponent_score INTEGER NOT NULL DEFAULT 0,
                result TEXT NOT NULL,
                date_played TEXT NOT NULL,
                notes TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY(player_id) REFERENCES players(id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                game_id INTEGER,
                timestamp TEXT NOT NULL,
                system_call TEXT NOT NULL,
                human_call TEXT,
                confidence REAL NOT NULL,
                bounce_x REAL NOT NULL,
                bounce_y REAL NOT NULL,
                court_zone TEXT NOT NULL,
                latency_ms REAL NOT NULL,
                fps REAL NOT NULL,
                error_distance_mm REAL,
                correct INTEGER,
                trajectory TEXT NOT NULL,
                FOREIGN KEY(game_id) REFERENCES games(id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS sessions (
                session_id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                user_id INTEGER,
                player_id INTEGER,
                player_name TEXT,
                teammate_name TEXT,
                opponent_1 TEXT,
                opponent_2 TEXT,
                input_mode TEXT NOT NULL DEFAULT 'simulation',
                FOREIGN KEY(user_id) REFERENCES users(id),
                FOREIGN KEY(player_id) REFERENCES players(id)
            )
            """
        )
        # Migration support for older v2 databases.
        if not column_exists(conn, "events", "game_id"):
            conn.execute("ALTER TABLE events ADD COLUMN game_id INTEGER")
        if not column_exists(conn, "sessions", "user_id"):
            conn.execute("ALTER TABLE sessions ADD COLUMN user_id INTEGER")
        if not column_exists(conn, "sessions", "player_id"):
            conn.execute("ALTER TABLE sessions ADD COLUMN player_id INTEGER")


def current_user() -> Optional[Dict[str, Any]]:
    user_id = session.get("user_id")
    if not user_id:
        return None
    with db() as conn:
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    return dict(row) if row else None


@app.context_processor
def inject_user():
    return {"current_user": current_user()}


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("user_id"):
            flash("Please log in first.", "warning")
            return redirect(url_for("login", next=request.path))
        return view(*args, **kwargs)

    return wrapped


def get_or_create_player_for_user(user_id: int, name: str) -> int:
    with db() as conn:
        row = conn.execute("SELECT id FROM players WHERE user_id = ? ORDER BY id LIMIT 1", (user_id,)).fetchone()
        if row:
            return int(row["id"])
        cur = conn.execute(
            "INSERT INTO players (user_id, player_name, team_name, created_at) VALUES (?, ?, ?, ?)",
            (user_id, name, "", datetime.now().isoformat(timespec="seconds")),
        )
        return int(cur.lastrowid)


def ensure_session() -> None:
    user = current_user()
    user_id = user["id"] if user else None
    player_name = session.get("player_name") or (user["full_name"] if user else "Player 1")
    player_id = session.get("player_id")
    if user_id and not player_id:
        player_id = get_or_create_player_for_user(user_id, player_name)
        session["player_id"] = player_id
    with db() as conn:
        conn.execute(
            """
            INSERT OR IGNORE INTO sessions
            (session_id, created_at, user_id, player_id, player_name, teammate_name, opponent_1, opponent_2, input_mode)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                SESSION_ID,
                datetime.now().isoformat(timespec="seconds"),
                user_id,
                player_id,
                player_name,
                session.get("teammate_name", "Teammate"),
                session.get("opponent_1", "Opponent 1"),
                session.get("opponent_2", "Opponent 2"),
                "simulation",
            ),
        )


def court_zone(x: float, y: float) -> str:
    side = "Left" if x < COURT_LENGTH_FT / 2 else "Right"
    zone = "Kitchen / NVZ" if 15 <= x <= 29 else "Back Court"
    lane = "Bottom Lane" if y < COURT_WIDTH_FT / 2 else "Top Lane"
    return f"{side} {zone} - {lane}"


def team_label(team_key: str) -> str:
    """Return the display name for Team A or Team B based on the current setup."""
    if team_key == "A":
        return f"{session.get('player_name', 'Player 1')} / {session.get('teammate_name', 'Teammate')}"
    return f"{session.get('opponent_1', 'Opponent 1')} / {session.get('opponent_2', 'Opponent 2')}"




def team_players(team_key: str) -> List[str]:
    """Return player names for Team A or Team B."""
    if team_key == "A":
        return [
            session.get("player_name", "Player 1"),
            session.get("teammate_name", "Teammate"),
        ]
    return [
        session.get("opponent_1", "Opponent 1"),
        session.get("opponent_2", "Opponent 2"),
    ]


def current_server_name(state: Optional[Dict[str, Any]] = None) -> str:
    """Return the player currently assigned to serve."""
    state = state or get_score_state()
    if not state.get("started") or int(state.get("server_number", 0)) == 0:
        return "Not assigned yet"
    players = team_players(str(state.get("serving_team", "A")))
    index = 0 if int(state.get("server_number", 1)) == 1 else 1
    return players[index]


def team_short_name(team_key: Optional[str]) -> Optional[str]:
    if team_key == "A":
        return "Team A"
    if team_key == "B":
        return "Team B"
    return None

def fresh_score_state(started: bool = False) -> Dict[str, Any]:
    """Create a side-out doubles pickleball score state.

    The dashboard uses the user's requested prototype display: before the game
    starts it shows 0-0-0. When the Start Game button is pressed, the first
    active server becomes Server 1 and the live call becomes 0-0-1.

    Note: official USA Pickleball side-out scoring normally starts doubles at
    0-0-2. To switch back to strict official scoring, change server_number to 2
    when start_score_state() is called.
    """
    return {
        "started": started,
        "team_a_score": 0,
        "team_b_score": 0,
        "serving_team": "A",
        "server_number": 1 if started else 0,
        "target_score": 11,
        "win_by": 2,
        "game_over": False,
        "last_action": "Ready to start. Pre-game display is 0-0-0.",
        "last_rally_winner": None,
        "last_point_team": None,
        "last_point_player": None,
    }


def start_score_state() -> Dict[str, Any]:
    """Begin the game using the requested prototype opening call 0-0-1."""
    state = fresh_score_state(started=True)
    state["last_action"] = f"Game started. {current_server_name(state)} will serve first."
    return state


def get_score_state() -> Dict[str, Any]:
    state = session.get("score_state")
    if not isinstance(state, dict):
        state = fresh_score_state(started=False)
        session["score_state"] = state
        session.modified = True
    # Small migration/default support if an older browser session is reused.
    defaults = fresh_score_state(started=bool(state.get("started", False)))
    changed = False
    for key, value in defaults.items():
        if key not in state:
            state[key] = value
            changed = True
    if state.get("serving_team") not in {"A", "B"}:
        state["serving_team"] = "A"
        changed = True
    allowed_server_numbers = {0, 1, 2}
    if int(state.get("server_number", 0)) not in allowed_server_numbers:
        state["server_number"] = 0 if not state.get("started") else 1
        changed = True
    if not state.get("started") and int(state.get("server_number", 0)) != 0:
        state["server_number"] = 0
        changed = True
    if state.get("started") and int(state.get("server_number", 0)) == 0:
        state["server_number"] = 1
        changed = True
    if changed:
        session["score_state"] = state
        session.modified = True
    return state


def serving_side_from_state(state: Optional[Dict[str, Any]] = None) -> str:
    """Return right/even or left/odd serving court based on serving score."""
    state = state or get_score_state()
    serving_team = str(state.get("serving_team", "A"))
    serving_score = int(state.get("team_a_score", 0)) if serving_team == "A" else int(state.get("team_b_score", 0))
    return "right" if serving_score % 2 == 0 else "left"


def serving_side_label(state: Optional[Dict[str, Any]] = None) -> str:
    side = serving_side_from_state(state)
    return "Right / Even" if side == "right" else "Left / Odd"


def service_marker_payload(state: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Coordinates used by the court map to show who serves and who receives.

    The canvas uses x=0..44 feet from Team A baseline to Team B baseline and
    y=0..20 feet across court width. This is a dashboard guide, not a referee
    calibration measurement.
    """
    state = state or get_score_state()
    serving_team = str(state.get("serving_team", "A"))
    receiving_team = "B" if serving_team == "A" else "A"
    side = serving_side_from_state(state)
    # In the drawing, bottom lane is treated as right/even and top lane as left/odd.
    server_y = 5.0 if side == "right" else 15.0
    receiver_y = 15.0 if side == "right" else 5.0
    server_x = 6.5 if serving_team == "A" else 37.5
    receiver_x = 37.5 if serving_team == "A" else 6.5
    return {
        "serving_team": serving_team,
        "receiving_team": receiving_team,
        "serving_side": side,
        "serving_side_label": serving_side_label(state),
        "receiving_side_label": "Diagonal return court",
        "server": {"x": server_x, "y": server_y, "label": current_server_name(state)},
        "receiver": {"x": receiver_x, "y": receiver_y, "label": team_label(receiving_team)},
    }


def score_payload() -> Dict[str, Any]:
    state = get_score_state()
    serving_team = state["serving_team"]
    receiving_team = "B" if serving_team == "A" else "A"
    serving_score = state["team_a_score"] if serving_team == "A" else state["team_b_score"]
    receiving_score = state["team_b_score"] if serving_team == "A" else state["team_a_score"]
    score_call = "0-0-0" if not state.get("started") else f"{serving_score}-{receiving_score}-{state['server_number']}"
    last_point_team = state.get("last_point_team")
    service_markers = service_marker_payload(state)
    return {
        **state,
        "team_a_name": team_label("A"),
        "team_b_name": team_label("B"),
        "team_a_players": team_players("A"),
        "team_b_players": team_players("B"),
        "serving_team_name": team_label(serving_team),
        "receiving_team_name": team_label(receiving_team),
        "current_server_name": current_server_name(state),
        "serving_score": serving_score,
        "receiving_score": receiving_score,
        "score_call": score_call,
        "score_call_words": score_call.replace("-", ", "),
        "serving_side": service_markers["serving_side"],
        "serving_side_label": service_markers["serving_side_label"],
        "receiving_side_label": service_markers["receiving_side_label"],
        "court_markers": service_markers,
        "last_point_team_name": team_label(last_point_team) if last_point_team in {"A", "B"} else "No point",
        "last_rally_winner_name": team_label(state.get("last_rally_winner")) if state.get("last_rally_winner") in {"A", "B"} else "No rally",
        "last_point_player": state.get("last_point_player") or "No point",
    }

def apply_rally_result(winner: str) -> Dict[str, Any]:
    """Update side-out doubles score after a rally.

    winner must be 'serving' or 'receiving'. In side-out scoring, only the
    serving team earns points. If the receiving team wins a rally, it is a
    server change or a side-out, not a point for the receiving team.
    """
    winner = winner.strip().lower()
    if winner not in {"serving", "receiving"}:
        raise ValueError("winner must be serving or receiving")

    state = get_score_state()
    if not state.get("started"):
        state.update(start_score_state())

    if state.get("game_over"):
        state["last_action"] = "Game is already finished. Reset the score to start another game."
        session["score_state"] = state
        session.modified = True
        return score_payload()

    serving_team = state["serving_team"]
    receiving_team = "B" if serving_team == "A" else "A"
    state["last_rally_winner"] = serving_team if winner == "serving" else receiving_team

    if winner == "serving":
        score_key = "team_a_score" if serving_team == "A" else "team_b_score"
        state[score_key] = int(state.get(score_key, 0)) + 1
        state["last_point_team"] = serving_team
        state["last_point_player"] = current_server_name(state)
        state["last_action"] = f"Point for {team_label(serving_team)}. {current_server_name(state)} continues from the {serving_side_label(state)} side."
    else:
        state["last_point_team"] = None
        state["last_point_player"] = None
        if int(state.get("server_number", 1)) == 1:
            state["server_number"] = 2
            state["last_action"] = f"{team_label(receiving_team)} won the rally. No point. Serve moves to Server 2: {current_server_name(state)}."
        else:
            state["serving_team"] = receiving_team
            state["server_number"] = 1
            state["last_action"] = f"Side-out. {team_label(receiving_team)} now serves from the {serving_side_label(state)} side."

    a = int(state.get("team_a_score", 0))
    b = int(state.get("team_b_score", 0))
    target = int(state.get("target_score", 11))
    win_by = int(state.get("win_by", 2))
    if max(a, b) >= target and abs(a - b) >= win_by:
        state["game_over"] = True
        winner_team = "A" if a > b else "B"
        state["last_action"] = f"Game over. Winner: {team_label(winner_team)}. Final score {a}-{b}."

    session["score_state"] = state
    session.modified = True
    return score_payload()


def generate_trajectory(bounce_x: float, bounce_y: float) -> List[Dict[str, float]]:
    start_x = max(1.0, bounce_x - random.uniform(10, 18))
    start_y = min(COURT_WIDTH_FT - 1.0, max(1.0, bounce_y + random.uniform(-5, 5)))
    points = []
    for i in range(7):
        t = i / 6
        curve = math.sin(t * math.pi) * random.uniform(1.2, 3.0)
        points.append(
            {
                "x": round(start_x + (bounce_x - start_x) * t, 2),
                "y": round(start_y + (bounce_y - start_y) * t + curve, 2),
            }
        )
    return points


def simulate_event() -> Dict[str, Any]:
    """Generate one mock event using the AI mock module.

    Later, replace this function so it calls the real AI pipeline instead of
    generate_mock_event(). The dashboard will still work as long as the returned
    dictionary keeps the same keys.
    """
    return generate_mock_event(SESSION_ID)



def require_ingest_key() -> Optional[Response]:
    """Protect external AI event ingestion when PICKLEVISION_API_KEY is set."""
    if not API_INGEST_KEY:
        return None
    provided = request.headers.get("X-PickleVision-Key", "")
    if provided != API_INGEST_KEY:
        return jsonify({"error": "Invalid or missing X-PickleVision-Key header"}), 401
    return None


def as_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def as_optional_float(value: Any) -> Optional[float]:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def normalize_event(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Convert AI/Raspberry Pi JSON into the event format used by the dashboard.

    Required useful fields from the AI side are only: system_call, confidence,
    bounce_x, and bounce_y. The rest are filled with safe defaults so the
    dashboard, reports, history, and CSV export continue to work.
    """
    system_call = str(
        payload.get("system_call")
        or payload.get("line_call")
        or payload.get("call")
        or ""
    ).strip().upper()
    if system_call not in {"IN", "OUT"}:
        raise ValueError("system_call must be IN or OUT")

    bounce_x = as_float(payload.get("bounce_x", payload.get("x")), 0.0)
    bounce_y = as_float(payload.get("bounce_y", payload.get("y")), 0.0)

    human_call_raw = payload.get("human_call")
    human_call = str(human_call_raw).strip().upper() if human_call_raw not in (None, "") else None
    if human_call not in {"IN", "OUT", None}:
        human_call = None

    correct = payload.get("correct")
    if correct is None and human_call is not None:
        correct = 1 if human_call == system_call else 0
    elif isinstance(correct, bool):
        correct = int(correct)
    elif correct in (0, 1, "0", "1"):
        correct = int(correct)
    else:
        correct = None

    trajectory = payload.get("trajectory") or []
    if not isinstance(trajectory, list):
        trajectory = []

    return {
        "session_id": str(payload.get("session_id") or SESSION_ID),
        "game_id": payload.get("game_id"),
        "timestamp": str(payload.get("timestamp") or datetime.now().isoformat(timespec="seconds")),
        "system_call": system_call,
        "human_call": human_call,
        "confidence": round(as_float(payload.get("confidence"), 0.0), 4),
        "bounce_x": round(bounce_x, 4),
        "bounce_y": round(bounce_y, 4),
        "court_zone": str(payload.get("court_zone") or court_zone(bounce_x, bounce_y)),
        "latency_ms": round(as_float(payload.get("latency_ms"), 0.0), 2),
        "fps": round(as_float(payload.get("fps"), 0.0), 2),
        "error_distance_mm": as_optional_float(payload.get("error_distance_mm")),
        "correct": correct,
        "trajectory": trajectory,
    }


def insert_event(event: Dict[str, Any]) -> None:
    ensure_session()
    with db() as conn:
        conn.execute(
            """
            INSERT INTO events
            (session_id, game_id, timestamp, system_call, human_call, confidence, bounce_x, bounce_y,
             court_zone, latency_ms, fps, error_distance_mm, correct, trajectory)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event["session_id"],
                event.get("game_id"),
                event["timestamp"],
                event["system_call"],
                event.get("human_call"),
                event["confidence"],
                event["bounce_x"],
                event["bounce_y"],
                event["court_zone"],
                event["latency_ms"],
                event["fps"],
                event.get("error_distance_mm"),
                event.get("correct"),
                json.dumps(event["trajectory"]),
            ),
        )


def maybe_create_simulated_event() -> None:
    global LAST_EVENT_TS
    # Only generate data after login to avoid filling database while public pages are viewed.
    if not session.get("user_id"):
        return
    with state_lock:
        now = time.time()
        if SIMULATION_ENABLED and now - LAST_EVENT_TS >= 2.0:
            insert_event(simulate_event())
            LAST_EVENT_TS = now


def rows_to_dicts(rows: List[sqlite3.Row]) -> List[Dict[str, Any]]:
    output = []
    for row in rows:
        item = dict(row)
        try:
            item["trajectory"] = json.loads(item.get("trajectory") or "[]")
        except Exception:
            try:
                item["trajectory"] = eval(item.get("trajectory") or "[]", {"__builtins__": {}})
            except Exception:
                item["trajectory"] = []
        output.append(item)
    return output


def get_recent_events(limit: int = 50) -> List[Dict[str, Any]]:
    with db() as conn:
        rows = conn.execute(
            "SELECT * FROM events WHERE session_id = ? ORDER BY id DESC LIMIT ?",
            (SESSION_ID, limit),
        ).fetchall()
    return rows_to_dicts(rows)[::-1]




def build_rally_trajectory(events: List[Dict[str, Any]], max_points: int = 300) -> List[Dict[str, Any]]:
    """Combine recent event trajectories into one visible rally trail.

    Each point is in court feet. If an event does not contain a frame-by-frame
    trajectory, its bounce coordinate is still included so the rally path remains
    visible.
    """
    combined: List[Dict[str, Any]] = []
    for event_index, event in enumerate(events):
        raw_points = event.get("trajectory") or []
        if not isinstance(raw_points, list) or not raw_points:
            raw_points = [{"x": event.get("bounce_x", 0), "y": event.get("bounce_y", 0)}]
        for point_index, point in enumerate(raw_points):
            try:
                x = float(point.get("x", 0))
                y = float(point.get("y", 0))
            except (AttributeError, TypeError, ValueError):
                continue
            combined.append({
                "x": round(x, 3),
                "y": round(y, 3),
                "event_index": event_index,
                "point_index": point_index,
                "system_call": event.get("system_call", ""),
            })
    return combined[-max_points:]

def get_all_user_events(user_id: int, limit: int = 1000) -> List[Dict[str, Any]]:
    with db() as conn:
        rows = conn.execute(
            """
            SELECT e.* FROM events e
            JOIN sessions s ON s.session_id = e.session_id
            WHERE s.user_id = ?
            ORDER BY e.id DESC LIMIT ?
            """,
            (user_id, limit),
        ).fetchall()
    return rows_to_dicts(rows)[::-1]


def compute_metrics(events: List[Dict[str, Any]]) -> Dict[str, Any]:
    total = len(events)
    in_calls = sum(1 for e in events if e["system_call"] == "IN")
    out_calls = sum(1 for e in events if e["system_call"] == "OUT")
    correct_events = [e for e in events if e.get("correct") is not None]
    correct = sum(int(e.get("correct") or 0) for e in correct_events)

    tp = sum(1 for e in correct_events if e["system_call"] == "IN" and e.get("human_call") == "IN")
    tn = sum(1 for e in correct_events if e["system_call"] == "OUT" and e.get("human_call") == "OUT")
    fp = sum(1 for e in correct_events if e["system_call"] == "IN" and e.get("human_call") == "OUT")
    fn = sum(1 for e in correct_events if e["system_call"] == "OUT" and e.get("human_call") == "IN")

    precision = tp / (tp + fp) if tp + fp else 0
    recall = tp / (tp + fn) if tp + fn else 0
    f1 = (2 * precision * recall / (precision + recall)) if precision + recall else 0

    avg_latency = sum(e["latency_ms"] for e in events) / total if total else 0
    max_latency = max((e["latency_ms"] for e in events), default=0)
    avg_fps = sum(e["fps"] for e in events) / total if total else 0
    avg_confidence = sum(e["confidence"] for e in events) / total if total else 0
    errors = [e["error_distance_mm"] for e in events if e.get("error_distance_mm") is not None]
    mae_mm = sum(errors) / len(errors) if errors else 0

    if psutil:
        cpu_usage = psutil.cpu_percent(interval=None)
        ram_usage = psutil.virtual_memory().percent
    else:
        cpu_usage = random.uniform(25, 60)
        ram_usage = random.uniform(35, 70)

    return {
        "total_shots": total,
        "in_calls": in_calls,
        "out_calls": out_calls,
        "accuracy": round(correct / len(correct_events), 3) if correct_events else 0,
        "precision": round(precision, 3),
        "recall": round(recall, 3),
        "f1_score": round(f1, 3),
        "tp": tp,
        "tn": tn,
        "fp": fp,
        "fn": fn,
        "avg_latency_ms": round(avg_latency, 1),
        "max_latency_ms": round(max_latency, 1),
        "avg_fps": round(avg_fps, 1),
        "avg_confidence": round(avg_confidence, 3),
        "mae_mm": round(mae_mm, 1),
        "cpu_usage": round(cpu_usage, 1),
        "ram_usage": round(ram_usage, 1),
    }


def player_stats(player_id: int) -> Dict[str, Any]:
    with db() as conn:
        games = conn.execute("SELECT * FROM games WHERE player_id = ? ORDER BY date_played DESC, id DESC", (player_id,)).fetchall()
    games_list = [dict(g) for g in games]
    total_games = len(games_list)
    wins = sum(1 for g in games_list if g["result"] == "Win")
    losses = sum(1 for g in games_list if g["result"] == "Loss")
    draws = sum(1 for g in games_list if g["result"] == "Draw")
    win_pct = (wins / total_games * 100) if total_games else 0
    return {
        "total_games": total_games,
        "wins": wins,
        "losses": losses,
        "draws": draws,
        "winning_percentage": round(win_pct, 1),
        "games": games_list,
    }


def get_events_for_player(player_id: int, limit: int = 1000) -> List[Dict[str, Any]]:
    """Return tracked ball events connected to one player session."""
    with db() as conn:
        rows = conn.execute(
            """
            SELECT e.* FROM events e
            JOIN sessions s ON s.session_id = e.session_id
            WHERE s.player_id = ?
            ORDER BY e.id DESC LIMIT ?
            """,
            (player_id, limit),
        ).fetchall()
    return rows_to_dicts(rows)[::-1]


def get_player_by_id(player_id: int) -> Optional[Dict[str, Any]]:
    with db() as conn:
        row = conn.execute(
            """
            SELECT p.*, u.full_name AS user_full_name, u.email, u.role
            FROM players p
            LEFT JOIN users u ON u.id = p.user_id
            WHERE p.id = ?
            """,
            (player_id,),
        ).fetchone()
    return dict(row) if row else None


def get_player_list() -> List[Dict[str, Any]]:
    """Return players intended for the coach dashboard."""
    with db() as conn:
        rows = conn.execute(
            """
            SELECT p.*, u.full_name AS user_full_name, u.email, u.role
            FROM players p
            LEFT JOIN users u ON u.id = p.user_id
            WHERE COALESCE(u.role, 'player') = 'player'
            ORDER BY p.player_name COLLATE NOCASE
            """
        ).fetchall()
    players = []
    for row in rows:
        item = dict(row)
        item["stats"] = player_stats(int(item["id"]))
        item["events_count"] = len(get_events_for_player(int(item["id"]), 2000))
        players.append(item)
    return players


def role_dashboard_endpoint(user: Dict[str, Any]) -> str:
    return "player_dashboard" if user.get("role") == "player" else "coach_dashboard"


@app.before_request
def before_request() -> None:
    init_db()
    if request.endpoint and request.endpoint.startswith("static"):
        return
    maybe_create_simulated_event()


@app.route("/")
@app.route("/landing")
def landing():
    return render_template("landing.html")


@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")
        role = request.form.get("role", "player").strip().lower()
        if role not in {"player", "coach"}:
            role = "player"

        if not full_name or not email or not password:
            flash("Please complete all required fields.", "error")
            return render_template("signup.html")

        if password != confirm:
            flash("Passwords do not match.", "error")
            return render_template("signup.html")

        try:
            # Create the user and player profile in the same DB connection to
            # avoid SQLite locking during sign up.
            with db() as conn:
                cur = conn.execute(
                    """
                    INSERT INTO users (full_name, email, password_hash, role, created_at)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (full_name, email, generate_password_hash(password), role, datetime.now().isoformat(timespec="seconds")),
                )
                user_id = int(cur.lastrowid)

                cur = conn.execute(
                    """
                    INSERT INTO players (user_id, player_name, team_name, created_at)
                    VALUES (?, ?, ?, ?)
                    """,
                    (user_id, full_name, "", datetime.now().isoformat(timespec="seconds")),
                )
                player_id = int(cur.lastrowid)

            session.clear()
            session["user_id"] = user_id
            session["player_id"] = player_id
            session["player_name"] = full_name
            flash("Account created successfully.", "success")
            return redirect(url_for("dashboard"))

        except sqlite3.IntegrityError:
            flash("That email is already registered.", "error")
            return render_template("signup.html")

    return render_template("signup.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        with db() as conn:
            row = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        if row and check_password_hash(row["password_hash"], password):
            user = dict(row)
            with db() as conn:
                player = conn.execute(
                    "SELECT id FROM players WHERE user_id = ? ORDER BY id LIMIT 1",
                    (user["id"],),
                ).fetchone()
                if player:
                    player_id = int(player["id"])
                else:
                    cur = conn.execute(
                        "INSERT INTO players (user_id, player_name, team_name, created_at) VALUES (?, ?, ?, ?)",
                        (user["id"], user["full_name"], "", datetime.now().isoformat(timespec="seconds")),
                    )
                    player_id = int(cur.lastrowid)

            session.clear()
            session["user_id"] = user["id"]
            session["player_name"] = user["full_name"]
            session["player_id"] = player_id
            flash("Logged in successfully.", "success")
            return redirect(request.args.get("next") or url_for("dashboard"))
        flash("Invalid email or password.", "error")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out.", "success")
    return redirect(url_for("login"))


@app.route("/setup", methods=["GET", "POST"])
@login_required
def setup():
    if request.method == "POST":
        session["player_name"] = request.form.get("player_name") or session.get("player_name", "Player 1")
        session["teammate_name"] = request.form.get("teammate_name") or "Teammate"
        session["opponent_1"] = request.form.get("opponent_1") or "Opponent 1"
        session["opponent_2"] = request.form.get("opponent_2") or "Opponent 2"
        # Update player profile name too.
        with db() as conn:
            conn.execute("UPDATE players SET player_name = ? WHERE id = ?", (session["player_name"], session.get("player_id")))
        # A new match setup begins with the requested pre-game display 0-0-0.
        session["score_state"] = fresh_score_state(started=False)
        session.modified = True
        ensure_session()
        return redirect(url_for("live_dashboard"))
    return render_template("setup.html")


@app.route("/dashboard")
@login_required
def dashboard():
    user = current_user() or {}
    return redirect(url_for(role_dashboard_endpoint(user)))


@app.route("/player-dashboard")
@login_required
def player_dashboard():
    user = current_user() or {}
    if user.get("role") != "player":
        return redirect(url_for("coach_dashboard"))

    player_id = session.get("player_id")
    if not player_id:
        player_id = get_or_create_player_for_user(int(user["id"]), user.get("full_name", "Player"))
        session["player_id"] = player_id
        session.modified = True

    player = get_player_by_id(int(player_id)) or {"player_name": user.get("full_name", "Player")}
    stats = player_stats(int(player_id))
    events = get_events_for_player(int(player_id), 500)
    if not events:
        events = get_all_user_events(int(user["id"]), 500)
    metrics = compute_metrics(events)
    trajectory_data = build_rally_trajectory(events[-10:], max_points=120)

    return render_template(
        "player_dashboard.html",
        player=player,
        stats=stats,
        metrics=metrics,
        events=events[-12:],
        trajectory_data=trajectory_data,
    )


@app.route("/coach-dashboard")
@login_required
def coach_dashboard():
    user = current_user() or {}
    if user.get("role") == "player":
        return redirect(url_for("player_dashboard"))

    players = get_player_list()
    selected_id_raw = request.args.get("player_id")
    try:
        selected_id = int(selected_id_raw) if selected_id_raw else (int(players[0]["id"]) if players else None)
    except (TypeError, ValueError):
        selected_id = int(players[0]["id"]) if players else None

    selected_player = get_player_by_id(selected_id) if selected_id else None
    selected_stats = player_stats(selected_id) if selected_id else {"total_games": 0, "wins": 0, "losses": 0, "draws": 0, "winning_percentage": 0, "games": []}
    selected_events = get_events_for_player(selected_id, 500) if selected_id else []
    selected_metrics = compute_metrics(selected_events)
    trajectory_data = build_rally_trajectory(selected_events[-10:], max_points=120)

    return render_template(
        "coach_dashboard.html",
        players=players,
        selected_player=selected_player,
        selected_stats=selected_stats,
        selected_events=selected_events[-12:],
        selected_metrics=selected_metrics,
        trajectory_data=trajectory_data,
    )


@app.route("/live-dashboard")
@login_required
def live_dashboard():
    return render_template(
        "dashboard.html",
        player_name=session.get("player_name", "Player 1"),
        teammate_name=session.get("teammate_name", "Teammate"),
        opponent_1=session.get("opponent_1", "Opponent 1"),
        opponent_2=session.get("opponent_2", "Opponent 2"),
    )


@app.route("/history")
@login_required
def history():
    return render_template("history.html")


@app.route("/calibration")
@login_required
def calibration():
    return render_template("calibration.html")


@app.route("/reports")
@login_required
def reports():
    return render_template("reports.html")


@app.route("/profile")
@login_required
def profile():
    player_id = int(session.get("player_id"))
    with db() as conn:
        player = conn.execute("SELECT * FROM players WHERE id = ?", (player_id,)).fetchone()
    events = get_all_user_events(int(session["user_id"]), 1000)
    return render_template("profile.html", player=dict(player), stats=player_stats(player_id), metrics=compute_metrics(events))


@app.route("/games")
@login_required
def games():
    player_id = int(session.get("player_id"))
    with db() as conn:
        rows = conn.execute("SELECT * FROM games WHERE player_id = ? ORDER BY date_played DESC, id DESC", (player_id,)).fetchall()
    return render_template("games.html", games=[dict(r) for r in rows], stats=player_stats(player_id))


@app.route("/games/new", methods=["GET", "POST"])
@login_required
def new_game():
    if request.method == "POST":
        player_id = int(session.get("player_id"))
        opponent_name = request.form.get("opponent_name", "Opponent").strip() or "Opponent"
        player_score = int(request.form.get("player_score") or 0)
        opponent_score = int(request.form.get("opponent_score") or 0)
        date_played = request.form.get("date_played") or datetime.now().date().isoformat()
        notes = request.form.get("notes", "").strip()
        if player_score > opponent_score:
            result = "Win"
        elif player_score < opponent_score:
            result = "Loss"
        else:
            result = "Draw"
        with db() as conn:
            conn.execute(
                """
                INSERT INTO games (player_id, opponent_name, player_score, opponent_score, result, date_played, notes, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (player_id, opponent_name, player_score, opponent_score, result, date_played, notes, datetime.now().isoformat(timespec="seconds")),
            )
        flash("Game record saved.", "success")
        return redirect(url_for("games"))
    return render_template("new_game.html", today=datetime.now().date().isoformat())


@app.route("/api/score")
@login_required
def api_score():
    return jsonify(score_payload())


@app.route("/api/score/start", methods=["POST"])
@login_required
def api_score_start():
    session["score_state"] = start_score_state()
    session.modified = True
    return jsonify(score_payload())


@app.route("/api/score/reset", methods=["POST"])
@login_required
def api_score_reset():
    session["score_state"] = fresh_score_state(started=False)
    session.modified = True
    return jsonify(score_payload())


@app.route("/api/score/rally", methods=["POST"])
@login_required
def api_score_rally():
    payload = request.get_json(silent=True) or {}
    try:
        return jsonify(apply_rally_result(str(payload.get("winner", ""))))
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400


@app.route("/api/update-live-data", methods=["POST"])
def api_update_live_data():
    """Receive one real AI event and save it to the current dashboard session.

    This is the bridge between the camera/AI code and the Flask dashboard.
    Example JSON:
    {
      "system_call": "IN",
      "confidence": 0.91,
      "bounce_x": 18.5,
      "bounce_y": 7.2,
      "latency_ms": 42.1,
      "fps": 24.8,
      "trajectory": [{"x": 12.0, "y": 8.0}, {"x": 18.5, "y": 7.2}]
    }
    """
    unauthorized = require_ingest_key()
    if unauthorized:
        return unauthorized

    payload = request.get_json(silent=True) or {}
    if not isinstance(payload, dict):
        return jsonify({"error": "JSON body must be an object"}), 400

    try:
        event = normalize_event(payload)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    insert_event(event)
    return jsonify({"saved": True, "event": event})


@app.route("/api/ai-status")
def api_ai_status():
    """Show model and simulation status for quick debugging."""
    try:
        from ai.detector import get_model_status
        model_status = get_model_status()
    except Exception as exc:  # pragma: no cover
        model_status = {"available": False, "loaded": False, "error": str(exc)}

    return jsonify({
        "session_id": SESSION_ID,
        "simulation_enabled": SIMULATION_ENABLED,
        "database": str(DB_PATH),
        "model": model_status,
        "ingest_key_required": bool(API_INGEST_KEY),
    })


@app.route("/api/live-data")
@login_required
def api_live_data():
    events = get_recent_events(100)
    latest = events[-1] if events else simulate_event()
    metrics = compute_metrics(events)

    # Draw only the current rally/shot path. Older independent simulated events
    # made the court map look messy because their paths overlapped. If a real AI
    # event sends a full trajectory list, that is what the dashboard shows.
    if isinstance(latest.get("trajectory"), list) and latest.get("trajectory"):
        rally_trajectory = latest["trajectory"]
    else:
        rally_trajectory = build_rally_trajectory(events[-3:], max_points=60)

    return jsonify({
        "latest": latest,
        "metrics": metrics,
        "events": events[-15:],
        "rally_trajectory": rally_trajectory,
        "simulation": SIMULATION_ENABLED,
        "score": score_payload(),
    })


@app.route("/api/events")
@login_required
def api_events():
    limit = int(request.args.get("limit", 100))
    return jsonify(get_recent_events(limit))


@app.route("/api/reports")
@login_required
def api_reports():
    events = get_recent_events(500)
    return jsonify({"metrics": compute_metrics(events), "events": events})


@app.route("/api/player-stats")
@login_required
def api_player_stats():
    player_id = int(session.get("player_id"))
    events = get_all_user_events(int(session["user_id"]), 1000)
    return jsonify({"player_stats": player_stats(player_id), "system_metrics": compute_metrics(events)})


@app.route("/api/toggle-simulation", methods=["POST"])
@login_required
def api_toggle_simulation():
    global SIMULATION_ENABLED
    SIMULATION_ENABLED = not SIMULATION_ENABLED
    return jsonify({"simulation": SIMULATION_ENABLED})


@app.route("/api/reset-session", methods=["POST"])
@login_required
def api_reset_session():
    global SESSION_ID, LAST_EVENT_TS
    SESSION_ID = datetime.now().strftime("S%Y%m%d%H%M%S")
    LAST_EVENT_TS = 0.0
    session["score_state"] = fresh_score_state(started=False)
    session.modified = True
    ensure_session()
    return jsonify({"session_id": SESSION_ID, "score": score_payload()})


@app.route("/api/export/events.csv")
@login_required
def export_events_csv():
    events = get_recent_events(1000)
    output = io.StringIO()
    writer = csv.DictWriter(
        output,
        fieldnames=[
            "id",
            "session_id",
            "timestamp",
            "system_call",
            "human_call",
            "confidence",
            "bounce_x",
            "bounce_y",
            "court_zone",
            "latency_ms",
            "fps",
            "error_distance_mm",
            "correct",
        ],
    )
    writer.writeheader()
    for e in events:
        row = {k: e.get(k) for k in writer.fieldnames}
        writer.writerow(row)
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=picklevision_events.csv"},
    )


@app.route("/api/export/games.csv")
@login_required
def export_games_csv():
    player_id = int(session.get("player_id"))
    with db() as conn:
        rows = conn.execute("SELECT * FROM games WHERE player_id = ? ORDER BY date_played DESC, id DESC", (player_id,)).fetchall()
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=["id", "opponent_name", "player_score", "opponent_score", "result", "date_played", "notes"])
    writer.writeheader()
    for row in rows:
        game = dict(row)
        writer.writerow({k: game.get(k) for k in writer.fieldnames})
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=picklevision_games.csv"},
    )




if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=5000, debug=True)