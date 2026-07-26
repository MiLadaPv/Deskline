"""Persist last tracker tick so hard power-off does not invent offline hours."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from deskline.config import DATA_ROOT, ensure_data_dirs

HEARTBEAT_NAME = "tracker_heartbeat.json"


def heartbeat_path() -> Path:
    return DATA_ROOT / HEARTBEAT_NAME


def load_heartbeat() -> dict[str, Any] | None:
    path = heartbeat_path()
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    try:
        sid = int(data.get("session_id"))
        tick = float(data.get("last_tick_at"))
    except (TypeError, ValueError):
        return None
    if sid <= 0 or tick <= 0:
        return None
    return {"session_id": sid, "last_tick_at": tick}


def save_heartbeat(session_id: int, last_tick_at: float | None = None) -> None:
    if session_id <= 0:
        return
    ensure_data_dirs()
    payload = {
        "session_id": int(session_id),
        "last_tick_at": float(last_tick_at if last_tick_at is not None else time.time()),
    }
    path = heartbeat_path()
    try:
        path.write_text(json.dumps(payload), encoding="utf-8")
    except OSError:
        pass


def clear_heartbeat() -> None:
    path = heartbeat_path()
    try:
        if path.is_file():
            path.unlink()
    except OSError:
        pass
