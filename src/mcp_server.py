from __future__ import annotations

import json
import logging

from mcp.server import MCPServer
from state_engine import capture, current_state, export_csv, history, recent_events

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

mcp = MCPServer("continuous-state-governance")

@mcp.tool()
def run_state_capture(application: str | None = None) -> str:
    """Run authoritative read-only state collectors now and compare observed state to approved baselines."""
    return json.dumps(capture(application), indent=2)

@mcp.tool()
def get_current_state(application: str | None = None) -> str:
    """Return the latest known state of all controls, optionally filtered by application id."""
    return json.dumps(current_state(application), indent=2)

@mcp.tool()
def get_control_history(control_id: str, limit: int = 20) -> str:
    """Return timestamped state history for one control."""
    return json.dumps(history(control_id, limit), indent=2)

@mcp.tool()
def get_recent_drift_events(limit: int = 30) -> str:
    """Return recent state transitions, drift detections, restorations, and collector failures."""
    return json.dumps(recent_events(limit), indent=2)

@mcp.tool()
def export_current_state_csv() -> str:
    """Export the latest state snapshot to a CSV evidence file and return its path."""
    return export_csv()

if __name__ == "__main__":
    mcp.run(transport="stdio")
