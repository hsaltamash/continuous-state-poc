from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path
from typing import Any

from common import ROOT
from state_engine import capture, export_csv


CONFIG_PATH = ROOT / "config" / "mock_app_config.json"


class DemoActionError(RuntimeError):
    pass


def _load_mock_config() -> dict[str, Any]:
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def _write_mock_config(data: dict[str, Any]) -> None:
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
        f.write("\n")


def _run(command: list[str], input_text: str | None = None) -> str:
    try:
        completed = subprocess.run(
            command,
            input=input_text,
            text=True,
            cwd=ROOT,
            capture_output=True,
            check=True,
            timeout=30,
        )
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or str(exc)).strip()
        raise DemoActionError(detail) from exc
    except subprocess.TimeoutExpired as exc:
        raise DemoActionError(f"Command timed out: {' '.join(command)}") from exc
    return (completed.stdout or completed.stderr or "OK").strip()


def _wait_for_mysql() -> None:
    command = [
        "docker",
        "exec",
        "csg-mysql",
        "mysqladmin",
        "ping",
        "-h",
        "127.0.0.1",
        "-uroot",
        "-proot_demo_pw",
        "--silent",
    ]
    deadline = time.monotonic() + 30
    last_error = "MySQL did not become ready."
    while time.monotonic() < deadline:
        try:
            _run(command)
            return
        except DemoActionError as exc:
            last_error = str(exc)
            time.sleep(1)
    raise DemoActionError(last_error)


def set_rest_drift(enabled: bool) -> str:
    data = _load_mock_config()
    data["security"]["session_timeout_minutes"] = 60 if enabled else 30
    _write_mock_config(data)
    return "REST session timeout drift applied." if enabled else "REST session timeout restored."


def set_file_drift(enabled: bool) -> str:
    data = _load_mock_config()
    data["security"]["tls_enabled"] = not enabled
    _write_mock_config(data)
    return "File TLS drift applied." if enabled else "File TLS setting restored."


def set_db_drift(enabled: bool) -> str:
    value = "350" if enabled else "200"
    _run(
        [
            "docker",
            "exec",
            "csg-mysql",
            "mysql",
            "--protocol=TCP",
            "-h127.0.0.1",
            "-uroot",
            "-proot_demo_pw",
            "demoapp",
            "-e",
            f"UPDATE app_config SET config_value='{value}' WHERE config_key='max_connections';",
        ]
    )
    return "Database max_connections drift applied." if enabled else "Database max_connections restored."


def set_iam_drift(enabled: bool) -> str:
    operation = "add" if enabled else "delete"
    ldif = f"""
dn: cn=app-admins,ou=groups,dc=demo,dc=local
changetype: modify
{operation}: member
member: uid=carol,ou=people,dc=demo,dc=local
""".lstrip()
    try:
        _run(
            [
                "docker",
                "exec",
                "-i",
                "csg-openldap",
                "ldapmodify",
                "-x",
                "-H",
                "ldap://127.0.0.1:389",
                "-D",
                "cn=admin,dc=demo,dc=local",
                "-w",
                "admin_demo_pw",
            ],
            input_text=ldif,
        )
    except DemoActionError as exc:
        text = str(exc)
        if enabled and "Type or value exists" in text:
            return "Carol is already in app-admins."
        if not enabled and "No such attribute" in text:
            return "Carol is already removed from app-admins."
        raise
    return "IAM group drift applied." if enabled else "IAM group membership restored."


def set_mysql_health(up: bool) -> str:
    _run(["docker", "start" if up else "stop", "csg-mysql"])
    if up:
        _wait_for_mysql()
    return "MySQL collector source started." if up else "MySQL collector source stopped."


def restore_all() -> str:
    messages = [
        set_mysql_health(True),
        set_rest_drift(False),
        set_file_drift(False),
        set_db_drift(False),
        set_iam_drift(False),
    ]
    return " ".join(messages)


def run_capture() -> str:
    results = capture("demo-web-app")
    counts: dict[str, int] = {}
    for result in results:
        counts[result["status"]] = counts.get(result["status"], 0) + 1
    summary = ", ".join(f"{status}: {count}" for status, count in sorted(counts.items()))
    return f"Capture complete ({summary})."


def export_evidence() -> str:
    path = Path(export_csv())
    return f"CSV evidence exported to {path.relative_to(ROOT)}."
