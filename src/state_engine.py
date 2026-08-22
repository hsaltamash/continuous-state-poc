from __future__ import annotations

import argparse
import csv
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from collectors import collect
from common import ROOT, canonical, db_path, load_config


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def connect_db() -> sqlite3.Connection:
    path = db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            captured_at TEXT NOT NULL,
            application_id TEXT NOT NULL,
            application_name TEXT NOT NULL,
            environment TEXT,
            owner TEXT,
            criticality TEXT,
            control_id TEXT NOT NULL,
            control_label TEXT,
            collector TEXT NOT NULL,
            expected_value TEXT,
            observed_value TEXT,
            status TEXT NOT NULL,
            collector_status TEXT NOT NULL,
            error TEXT,
            tags TEXT,
            compliance TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_snapshots_control_time
          ON snapshots(application_id, control_id, captured_at);

        CREATE TABLE IF NOT EXISTS drift_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            detected_at TEXT NOT NULL,
            application_id TEXT NOT NULL,
            control_id TEXT NOT NULL,
            previous_status TEXT,
            new_status TEXT NOT NULL,
            previous_value TEXT,
            new_value TEXT,
            event_type TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS collector_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_at TEXT NOT NULL,
            application_id TEXT NOT NULL,
            control_id TEXT NOT NULL,
            collector TEXT NOT NULL,
            status TEXT NOT NULL,
            error TEXT
        );
        """
    )
    conn.commit()


def previous_snapshot(conn: sqlite3.Connection, app_id: str, control_id: str) -> sqlite3.Row | None:
    return conn.execute(
        """SELECT * FROM snapshots
           WHERE application_id=? AND control_id=?
           ORDER BY id DESC LIMIT 1""",
        (app_id, control_id),
    ).fetchone()


def capture(application_filter: str | None = None) -> list[dict[str, Any]]:
    cfg = load_config()
    conn = connect_db()
    init_db(conn)
    results: list[dict[str, Any]] = []
    captured_at = utc_now()

    for app in cfg["applications"]:
        if application_filter and app["id"] != application_filter:
            continue
        for control in app["controls"]:
            prev = previous_snapshot(conn, app["id"], control["id"])
            expected = canonical(control.get("expected"))
            observed = None
            status = "UNKNOWN"
            collector_status = "ERROR"
            error = None

            try:
                raw = collect(control)
                observed = canonical(raw)
                collector_status = "OK"
                status = "MATCH" if observed == expected else "DRIFT"
            except Exception as exc:
                error = f"{type(exc).__name__}: {exc}"

            conn.execute(
                """INSERT INTO collector_runs(run_at, application_id, control_id, collector, status, error)
                   VALUES(?,?,?,?,?,?)""",
                (captured_at, app["id"], control["id"], control["collector"], collector_status, error),
            )

            conn.execute(
                """INSERT INTO snapshots(
                    captured_at, application_id, application_name, environment, owner, criticality,
                    control_id, control_label, collector, expected_value, observed_value,
                    status, collector_status, error, tags, compliance
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    captured_at, app["id"], app.get("name", app["id"]), app.get("environment"),
                    app.get("owner"), app.get("criticality"), control["id"], control.get("label"),
                    control["collector"], expected, observed, status, collector_status, error,
                    json.dumps(app.get("tags", [])), control.get("compliance"),
                ),
            )

            if prev is None:
                event_type = "INITIAL_STATE"
                changed = True
            else:
                changed = prev["status"] != status or prev["observed_value"] != observed
                if prev["status"] == "MATCH" and status == "DRIFT":
                    event_type = "DRIFT_DETECTED"
                elif prev["status"] == "DRIFT" and status == "MATCH":
                    event_type = "DRIFT_RESTORED"
                elif status == "UNKNOWN" and prev["status"] != "UNKNOWN":
                    event_type = "COLLECTOR_LOST"
                elif prev["status"] == "UNKNOWN" and status != "UNKNOWN":
                    event_type = "COLLECTOR_RESTORED"
                else:
                    event_type = "STATE_CHANGED"

            if changed:
                conn.execute(
                    """INSERT INTO drift_events(
                        detected_at, application_id, control_id, previous_status, new_status,
                        previous_value, new_value, event_type
                    ) VALUES(?,?,?,?,?,?,?,?)""",
                    (
                        captured_at, app["id"], control["id"], prev["status"] if prev else None,
                        status, prev["observed_value"] if prev else None, observed, event_type,
                    ),
                )

            results.append(
                {
                    "captured_at": captured_at,
                    "application_id": app["id"],
                    "control_id": control["id"],
                    "label": control.get("label"),
                    "collector": control["collector"],
                    "expected": expected,
                    "observed": observed,
                    "status": status,
                    "collector_status": collector_status,
                    "error": error,
                }
            )

    conn.commit()
    conn.close()
    return results


def current_state(application_filter: str | None = None) -> list[dict[str, Any]]:
    conn = connect_db()
    init_db(conn)
    params: list[Any] = []
    where = ""
    if application_filter:
        where = "WHERE s.application_id=?"
        params.append(application_filter)
    rows = conn.execute(
        f"""
        SELECT s.* FROM snapshots s
        JOIN (
            SELECT application_id, control_id, MAX(id) max_id
            FROM snapshots GROUP BY application_id, control_id
        ) latest ON s.id=latest.max_id
        {where}
        ORDER BY s.application_id, s.control_id
        """,
        params,
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def history(control_id: str, limit: int = 20) -> list[dict[str, Any]]:
    conn = connect_db()
    init_db(conn)
    rows = conn.execute(
        """SELECT captured_at, application_id, control_id, expected_value, observed_value,
                  status, collector_status, error
           FROM snapshots WHERE control_id=? ORDER BY id DESC LIMIT ?""",
        (control_id, limit),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def recent_events(limit: int = 50) -> list[dict[str, Any]]:
    conn = connect_db()
    init_db(conn)
    rows = conn.execute(
        "SELECT * FROM drift_events ORDER BY id DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def export_csv(path: str | None = None) -> str:
    rows = current_state()
    out = Path(path) if path else ROOT / "output" / f"state-{datetime.now().strftime('%Y%m%d-%H%M%S')}.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    if rows:
        with open(out, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=rows[0].keys())
            writer.writeheader()
            writer.writerows(rows)
    return str(out)


def main() -> None:
    parser = argparse.ArgumentParser(description="Continuous State Governance PoC")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_capture = sub.add_parser("capture")
    p_capture.add_argument("--app")
    p_current = sub.add_parser("current")
    p_current.add_argument("--app")
    p_hist = sub.add_parser("history")
    p_hist.add_argument("control_id")
    p_hist.add_argument("--limit", type=int, default=20)
    p_events = sub.add_parser("events")
    p_events.add_argument("--limit", type=int, default=50)
    p_export = sub.add_parser("export-csv")
    p_export.add_argument("--path")

    args = parser.parse_args()
    if args.cmd == "capture":
        print(json.dumps(capture(args.app), indent=2))
    elif args.cmd == "current":
        print(json.dumps(current_state(args.app), indent=2))
    elif args.cmd == "history":
        print(json.dumps(history(args.control_id, args.limit), indent=2))
    elif args.cmd == "events":
        print(json.dumps(recent_events(args.limit), indent=2))
    elif args.cmd == "export-csv":
        print(export_csv(args.path))


if __name__ == "__main__":
    main()
