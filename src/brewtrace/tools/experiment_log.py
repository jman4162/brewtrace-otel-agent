"""SQLite experiment logger — stdlib only, database in data/brewtrace.db."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from strands import tool

from brewtrace.models import BrewLog, Recommendation

DEFAULT_DB = Path(__file__).resolve().parents[3] / "data" / "brewtrace.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS experiments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    brew_json TEXT NOT NULL,
    defect TEXT,
    variable TEXT NOT NULL,
    direction TEXT NOT NULL,
    rationale TEXT NOT NULL
)
"""


def get_conn(db_path: Path = DEFAULT_DB) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute(_SCHEMA)
    return conn


def log_experiment(brew: BrewLog, rec: Recommendation, db_path: Path = DEFAULT_DB) -> int:
    with get_conn(db_path) as conn:
        cursor = conn.execute(
            "INSERT INTO experiments (ts, brew_json, defect, variable, direction, rationale) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                datetime.now(timezone.utc).isoformat(),
                brew.model_dump_json(),
                brew.defect.value if brew.defect else None,
                rec.adjustment.variable.value,
                rec.adjustment.direction.value,
                rec.adjustment.rationale,
            ),
        )
        return int(cursor.lastrowid)


def recent_experiments(limit: int = 5, db_path: Path = DEFAULT_DB) -> list[dict]:
    with get_conn(db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT id, ts, brew_json, defect, variable, direction, rationale "
            "FROM experiments ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
    results = []
    for row in rows:
        record = dict(row)
        record["brew"] = json.loads(record.pop("brew_json"))
        results.append(record)
    return results


@tool
def log_brew_experiment(brew_log_json: str, recommendation_json: str) -> str:
    """Save a brew log and its recommendation to the local experiment database.

    Args:
        brew_log_json: The BrewLog as JSON
        recommendation_json: The Recommendation as JSON, with adjustment
            {variable, direction, magnitude, rationale} and confidence
    """
    brew = BrewLog.model_validate_json(brew_log_json)
    rec = Recommendation.model_validate_json(recommendation_json)
    row_id = log_experiment(brew, rec)
    return f"Logged experiment #{row_id}."


@tool
def get_recent_experiments(limit: int = 5) -> str:
    """Fetch the most recent logged brew experiments, newest first.

    Args:
        limit: Maximum number of experiments to return
    """
    rows = recent_experiments(limit=limit)
    if not rows:
        return "No experiments logged yet."
    lines = []
    for row in rows:
        lines.append(
            f"#{row['id']} {row['ts'][:16]} defect={row['defect'] or '—'} "
            f"→ {row['variable']} {row['direction']}"
        )
    return "\n".join(lines)
