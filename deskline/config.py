from __future__ import annotations

import json
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any

APP_NAME = "Deskline"
HOST = "127.0.0.1"
PORT = 8787
BASE_URL = f"http://{HOST}:{PORT}"

PACKAGE_ROOT = Path(__file__).resolve().parent


def _project_root() -> Path:
    # PyInstaller onedir/onefile extracts/bundles resources here
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)
    return PACKAGE_ROOT.parent


PROJECT_ROOT = _project_root()
WEB_ROOT = PROJECT_ROOT / "web"

DATA_ROOT = Path.home() / "AppData" / "Local" / "Deskline"
DB_PATH = DATA_ROOT / "deskline.db"
SCREENSHOTS_DIR = DATA_ROOT / "screenshots"
CONFIG_PATH = DATA_ROOT / "config.json"

DEFAULT_CONFIG: dict[str, Any] = {
    "poll_interval_sec": 2.0,
    "min_session_sec": 3.0,
    "screenshot_interval_sec": 300,
    "screenshot_on_app_switch": True,
    "screenshots_enabled": True,
    "screenshot_retention_days": 7,
    "open_dashboard_on_start": True,
    "autostart": False,
    "paused": False,
}


def ensure_data_dirs() -> None:
    DATA_ROOT.mkdir(parents=True, exist_ok=True)
    SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)


def load_config() -> dict[str, Any]:
    ensure_data_dirs()
    cfg = deepcopy(DEFAULT_CONFIG)
    if CONFIG_PATH.exists():
        try:
            raw = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                cfg.update({k: raw[k] for k in DEFAULT_CONFIG if k in raw})
        except (OSError, json.JSONDecodeError):
            pass
    return cfg


def save_config(cfg: dict[str, Any]) -> dict[str, Any]:
    ensure_data_dirs()
    merged = deepcopy(DEFAULT_CONFIG)
    merged.update({k: cfg[k] for k in DEFAULT_CONFIG if k in cfg})
    CONFIG_PATH.write_text(json.dumps(merged, indent=2), encoding="utf-8")
    return merged
