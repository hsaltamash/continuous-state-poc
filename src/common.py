from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")


def load_config() -> dict[str, Any]:
    config_file = os.getenv("CSG_CONFIG_FILE", "config/onboarding.yaml")
    path = Path(config_file)
    if not path.is_absolute():
        path = ROOT / path
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def get_by_path(data: Any, dotted_path: str) -> Any:
    cur = data
    for part in dotted_path.split("."):
        if isinstance(cur, dict):
            cur = cur[part]
        else:
            raise KeyError(f"Cannot resolve '{part}' in path '{dotted_path}'")
    return cur


def canonical(value: Any) -> str:
    if isinstance(value, list):
        value = sorted(value)
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def resolve_password(control: dict[str, Any]) -> str:
    env_name = control.get("password_env")
    if not env_name:
        return ""
    value = os.getenv(env_name)
    if value is None:
        raise RuntimeError(f"Required environment variable {env_name} is not set")
    return value


def db_path() -> Path:
    cfg = load_config()
    return ROOT / cfg["platform"]["state_db"]
