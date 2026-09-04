import os

from flask import Flask, flash, redirect, render_template, url_for

from demo_actions import (
    DemoActionError,
    export_evidence,
    restore_all,
    run_capture,
    set_db_drift,
    set_file_drift,
    set_iam_drift,
    set_mysql_health,
    set_rest_drift,
)
from state_engine import current_state, recent_events

app = Flask(__name__, template_folder="../templates")
app.secret_key = "continuous-state-governance-demo"

@app.get("/")
def index():
    rows = current_state()
    counts = {"MATCH": 0, "DRIFT": 0, "UNKNOWN": 0}
    for row in rows:
        counts[row["status"]] = counts.get(row["status"], 0) + 1
    row_by_control = {row["control_id"]: row for row in rows}
    return render_template(
        "dashboard.html",
        rows=rows,
        row_by_control=row_by_control,
        events=recent_events(20),
        counts=counts,
    )


def _run_action(action):
    try:
        flash(action(), "success")
    except DemoActionError as exc:
        flash(str(exc), "error")
    return redirect(url_for("index"))


@app.post("/capture")
def capture_now():
    return _run_action(run_capture)


@app.post("/demo/rest-drift/apply")
def apply_rest_drift():
    return _run_action(lambda: set_rest_drift(True))


@app.post("/demo/rest-drift/restore")
def restore_rest_drift():
    return _run_action(lambda: set_rest_drift(False))


@app.post("/demo/file-drift/apply")
def apply_file_drift():
    return _run_action(lambda: set_file_drift(True))


@app.post("/demo/file-drift/restore")
def restore_file_drift():
    return _run_action(lambda: set_file_drift(False))


@app.post("/demo/db-drift/apply")
def apply_db_drift():
    return _run_action(lambda: set_db_drift(True))


@app.post("/demo/db-drift/restore")
def restore_db_drift():
    return _run_action(lambda: set_db_drift(False))


@app.post("/demo/iam-drift/apply")
def apply_iam_drift():
    return _run_action(lambda: set_iam_drift(True))


@app.post("/demo/iam-drift/restore")
def restore_iam_drift():
    return _run_action(lambda: set_iam_drift(False))


@app.post("/demo/mysql-health/down")
def mysql_health_down():
    return _run_action(lambda: set_mysql_health(False))


@app.post("/demo/mysql-health/up")
def mysql_health_up():
    return _run_action(lambda: set_mysql_health(True))


@app.post("/demo/restore-all")
def restore_everything():
    return _run_action(restore_all)


@app.post("/export-csv")
def export_csv_evidence():
    return _run_action(export_evidence)

if __name__ == "__main__":
    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", "5002"))
    app.run(host=host, port=port, debug=False)
