from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import mysql.connector
import requests
from ldap3 import BASE, Connection, Server

from common import ROOT, get_by_path, resolve_password


def collect_file_json(control: dict[str, Any]) -> Any:
    path = ROOT / control["file"]
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return get_by_path(data, control["path"])


def collect_rest_json(control: dict[str, Any]) -> Any:
    response = requests.get(control["endpoint"], timeout=5)
    response.raise_for_status()
    return get_by_path(response.json(), control["path"])


def collect_mysql_query(control: dict[str, Any]) -> Any:
    conn = mysql.connector.connect(
        host=control["host"],
        port=int(control.get("port", 3306)),
        database=control["database"],
        user=control["user"],
        password=resolve_password(control),
        connection_timeout=5,
    )
    try:
        cursor = conn.cursor()
        cursor.execute(control["query"])
        row = cursor.fetchone()
        if row is None:
            raise RuntimeError("Query returned no rows")
        return row[0]
    finally:
        conn.close()


def collect_ldap_group_members(control: dict[str, Any]) -> Any:
    server = Server(control["host"], port=int(control.get("port", 389)), connect_timeout=5)
    conn = Connection(
        server,
        user=control["bind_dn"],
        password=resolve_password(control),
        auto_bind=True,
    )
    try:
        ok = conn.search(
            search_base=control["group_dn"],
            search_filter="(objectClass=*)",
            search_scope=BASE,
            attributes=["member"],
        )
        if not ok or not conn.entries:
            raise RuntimeError(f"LDAP group not found: {control['group_dn']}")
        values = conn.entries[0]["member"].values
        return sorted(str(v) for v in values)
    finally:
        conn.unbind()


COLLECTORS = {
    "file_json": collect_file_json,
    "rest_json": collect_rest_json,
    "mysql_query": collect_mysql_query,
    "ldap_group_members": collect_ldap_group_members,
}


def collect(control: dict[str, Any]) -> Any:
    collector_name = control["collector"]
    if collector_name not in COLLECTORS:
        raise ValueError(f"Unknown collector: {collector_name}")
    return COLLECTORS[collector_name](control)
