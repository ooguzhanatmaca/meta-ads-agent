"""Persistent memory for the agent: metric snapshots + a recommendation journal.

This turns the agent from a stateless analyst into an ongoing advisor: it can
record the advice it gives, store daily metric snapshots, and later review
whether past recommendations were followed and how the metric moved.

Storage is a local SQLite file (stdlib ``sqlite3`` — no extra dependency). All
functions take an explicit ``conn`` so they are pure and easy to test with an
in-memory database.
"""

from __future__ import annotations

import os
import sqlite3
from datetime import date
from typing import Any, Iterable


# Metrics tracked over time. Keep this list stable; adding one means a new column.
TRACKED_METRICS = ("spend", "roas", "cpa", "ctr", "cpm", "cpc", "frequency", "purchases")

# Recommendation actions the agent may log (free text also allowed, these guide it).
KNOWN_ACTIONS = (
    "pause",
    "activate",
    "scale_up",
    "reduce_budget",
    "reallocate_budget",
    "clone_winner",
    "test_lookalike",
    "refresh_creative",
    "new_audience",
    "other",
)

VALID_STATUSES = ("open", "followed", "dismissed")


def default_db_path() -> str:
    """Location of the history database (override with HISTORY_DB_PATH)."""
    env = os.getenv("HISTORY_DB_PATH", "").strip()
    if env:
        return env
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return os.path.join(root, "data", "history.db")


def connect(db_path: str | None = None) -> sqlite3.Connection:
    """Open (creating the file/dir and tables if needed) the history database.

    Pass ``":memory:"`` for an ephemeral DB in tests.
    """
    path = db_path or default_db_path()
    if path != ":memory:":
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    _create_schema(conn)
    return conn


def _create_schema(conn: sqlite3.Connection) -> None:
    metric_columns = ", ".join(f"{name} REAL" for name in TRACKED_METRICS)
    conn.executescript(
        f"""
        CREATE TABLE IF NOT EXISTS snapshots (
            taken_on    TEXT NOT NULL,
            account_id  TEXT NOT NULL DEFAULT '-',
            level       TEXT NOT NULL,
            entity_id   TEXT NOT NULL,
            entity_name TEXT NOT NULL DEFAULT '-',
            status      TEXT NOT NULL DEFAULT '-',
            {metric_columns},
            PRIMARY KEY (taken_on, account_id, level, entity_id)
        );

        CREATE TABLE IF NOT EXISTS recommendations (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            created_on   TEXT NOT NULL,
            account_id   TEXT NOT NULL DEFAULT '-',
            level        TEXT NOT NULL,
            entity_id    TEXT NOT NULL,
            entity_name  TEXT NOT NULL DEFAULT '-',
            action       TEXT NOT NULL,
            reason       TEXT NOT NULL DEFAULT '',
            metric_name  TEXT NOT NULL DEFAULT '',
            metric_value REAL,
            status       TEXT NOT NULL DEFAULT 'open',
            outcome_note TEXT
        );
        """
    )
    conn.commit()


def _today() -> str:
    return date.today().isoformat()


def save_snapshot(
    conn: sqlite3.Connection,
    level: str,
    rows: Iterable[dict[str, Any]],
    *,
    account_id: str = "-",
    taken_on: str | None = None,
) -> int:
    """Upsert one snapshot row per entity for the given day.

    Re-running on the same day overwrites that day's values (idempotent), so the
    daily cron can run safely more than once. Returns the number of rows written.
    """
    day = taken_on or _today()
    metric_cols = ", ".join(TRACKED_METRICS)
    placeholders = ", ".join("?" for _ in TRACKED_METRICS)
    sql = (
        f"INSERT INTO snapshots "
        f"(taken_on, account_id, level, entity_id, entity_name, status, {metric_cols}) "
        f"VALUES (?, ?, ?, ?, ?, ?, {placeholders}) "
        f"ON CONFLICT(taken_on, account_id, level, entity_id) DO UPDATE SET "
        f"entity_name=excluded.entity_name, status=excluded.status, "
        + ", ".join(f"{m}=excluded.{m}" for m in TRACKED_METRICS)
    )
    count = 0
    for row in rows:
        values = [
            day,
            account_id,
            level,
            str(row.get("id") or row.get("entity_id") or "-"),
            str(row.get("name") or row.get("entity_name") or "-"),
            str(row.get("status") or "-"),
            *[float(row.get(metric) or 0.0) for metric in TRACKED_METRICS],
        ]
        conn.execute(sql, values)
        count += 1
    conn.commit()
    return count


def metric_history(
    conn: sqlite3.Connection,
    level: str,
    entity_id: str,
    metric: str,
    *,
    account_id: str = "-",
    limit: int = 30,
) -> list[dict[str, Any]]:
    """Return the stored time series for one metric of one entity (oldest first)."""
    if metric not in TRACKED_METRICS:
        raise ValueError(f"Bilinmeyen metrik: {metric}. Geçerli: {', '.join(TRACKED_METRICS)}")
    cursor = conn.execute(
        f"SELECT taken_on, entity_name, status, {metric} AS value FROM snapshots "
        f"WHERE level = ? AND entity_id = ? AND account_id = ? "
        f"ORDER BY taken_on DESC LIMIT ?",
        (level, entity_id, account_id, limit),
    )
    rows = [dict(row) for row in cursor.fetchall()]
    rows.reverse()
    return rows


def find_entity_id(
    conn: sqlite3.Connection,
    level: str,
    name_query: str,
    *,
    account_id: str = "-",
) -> dict[str, str] | None:
    """Resolve a (partial) entity name to its id using the snapshot history."""
    cursor = conn.execute(
        "SELECT entity_id, entity_name FROM snapshots "
        "WHERE level = ? AND account_id = ? AND entity_name LIKE ? "
        "ORDER BY taken_on DESC LIMIT 1",
        (level, account_id, f"%{name_query}%"),
    )
    row = cursor.fetchone()
    return {"entity_id": row["entity_id"], "entity_name": row["entity_name"]} if row else None


def record_recommendation(
    conn: sqlite3.Connection,
    *,
    level: str,
    entity_id: str,
    entity_name: str,
    action: str,
    reason: str = "",
    metric_name: str = "",
    metric_value: float | None = None,
    account_id: str = "-",
    created_on: str | None = None,
) -> int:
    """Append a recommendation to the journal. Returns the new row id."""
    cursor = conn.execute(
        "INSERT INTO recommendations "
        "(created_on, account_id, level, entity_id, entity_name, action, reason, "
        " metric_name, metric_value, status) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'open')",
        (
            created_on or _today(),
            account_id,
            level,
            str(entity_id),
            str(entity_name),
            action,
            reason,
            metric_name,
            metric_value,
            ),
    )
    conn.commit()
    return int(cursor.lastrowid)


def list_recommendations(
    conn: sqlite3.Connection,
    *,
    status: str | None = "open",
    account_id: str = "-",
    limit: int = 50,
) -> list[dict[str, Any]]:
    """List journalled recommendations, newest first (optionally by status)."""
    if status:
        cursor = conn.execute(
            "SELECT * FROM recommendations WHERE status = ? AND account_id = ? "
            "ORDER BY created_on DESC, id DESC LIMIT ?",
            (status, account_id, limit),
        )
    else:
        cursor = conn.execute(
            "SELECT * FROM recommendations WHERE account_id = ? "
            "ORDER BY created_on DESC, id DESC LIMIT ?",
            (account_id, limit),
        )
    return [dict(row) for row in cursor.fetchall()]


def update_recommendation(
    conn: sqlite3.Connection,
    rec_id: int,
    *,
    status: str | None = None,
    outcome_note: str | None = None,
) -> bool:
    """Update a recommendation's status and/or outcome note. Returns True if found."""
    if status is not None and status not in VALID_STATUSES:
        raise ValueError(f"Geçersiz durum: {status}. Geçerli: {', '.join(VALID_STATUSES)}")
    sets, params = [], []
    if status is not None:
        sets.append("status = ?")
        params.append(status)
    if outcome_note is not None:
        sets.append("outcome_note = ?")
        params.append(outcome_note)
    if not sets:
        return False
    params.append(rec_id)
    cursor = conn.execute(
        f"UPDATE recommendations SET {', '.join(sets)} WHERE id = ?", params
    )
    conn.commit()
    return cursor.rowcount > 0


def evaluate_outcome(
    metric_name: str,
    before: float | None,
    after: float | None,
) -> dict[str, Any]:
    """Compare a recommendation's metric before vs. now and judge the direction.

    For cost metrics (cpa, cpc, cpm) lower is better; for the rest higher is
    better. ``frequency`` is treated as a cost (lower is healthier). Returns a
    verdict dict with a human-readable Turkish note.
    """
    lower_is_better = metric_name in {"cpa", "cpc", "cpm", "frequency", "spend"}
    if before is None or after is None or not metric_name:
        return {"verdict": "bilinmiyor", "delta_pct": None, "note": "Karşılaştırma için yeterli veri yok."}
    if before == 0:
        return {"verdict": "bilinmiyor", "delta_pct": None, "note": "Önceki değer sıfır; oran hesaplanamadı."}

    delta_pct = (after - before) / abs(before) * 100
    improved = (after < before) if lower_is_better else (after > before)
    if abs(delta_pct) < 5:
        verdict = "nötr"
    elif improved:
        verdict = "iyileşti"
    else:
        verdict = "kötüleşti"
    arrow = "↓" if after < before else ("↑" if after > before else "→")
    note = (
        f"{metric_name.upper()} {before:.2f} {arrow} {after:.2f} "
        f"(%{delta_pct:+.0f}) — {verdict}."
    )
    return {"verdict": verdict, "delta_pct": delta_pct, "note": note}
