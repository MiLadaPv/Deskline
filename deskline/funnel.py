"""Local funnel event log for GTM metrics (no cloud)."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from deskline.config import DATA_ROOT, ensure_data_dirs

FUNNEL_NAME = "funnel.jsonl"
ALLOWED = frozenset(
    {
        "app_first_open",
        "trial_start",
        "welcome_view",
        "download_view",
        "download_click",
        "pro_activate",
        "team_activate",
        "extension_paired",
    }
)


def funnel_path() -> Path:
    return DATA_ROOT / FUNNEL_NAME


def record_funnel_event(name: str, meta: dict[str, Any] | None = None) -> bool:
    event = (name or "").strip().lower()
    if event not in ALLOWED:
        return False
    ensure_data_dirs()
    row = {
        "ts": time.time(),
        "event": event,
        "meta": meta or {},
    }
    path = funnel_path()
    try:
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    except OSError:
        return False
    return True


def read_funnel_tail(limit: int = 100) -> list[dict[str, Any]]:
    path = funnel_path()
    if not path.is_file():
        return []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    out: list[dict[str, Any]] = []
    for line in lines[-max(1, min(limit, 500)) :]:
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out
