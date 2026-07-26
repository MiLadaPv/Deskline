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

# Public brand / legal (shown in footer and /about|/privacy|/terms)
COMPANY_NAME = "AndalusGames"
SUPPORT_EMAIL = "milanochka.llc@gmail.com"
GITHUB_URL = "https://github.com/MiLadaPv/Deskline"
GITHUB_RELEASES_URL = f"{GITHUB_URL}/releases"
LEGAL_JURISDICTION = "Hashemite Kingdom of Jordan"

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
ICONS_DIR = DATA_ROOT / "icons"
CONFIG_PATH = DATA_ROOT / "config.json"

DEFAULT_CONFIG: dict[str, Any] = {
    "poll_interval_sec": 2.0,
    "min_session_sec": 3.0,
    # No keyboard/mouse for this long → idle (TD-style; does not cut productive time)
    "idle_after_sec": 180.0,
    # After idle + this grace → "Are you still working?"
    "still_working_grace_sec": 60.0,
    # Wall-clock gap between ticks treated as sleep/suspend (not counted)
    "sleep_gap_sec": 120.0,
    "poor_time_popup": True,
    "poor_time_min_sec": 60.0,
    "blur_screenshots": False,
    "screenshot_interval_sec": 300,
    "screenshot_on_app_switch": True,
    "screenshots_enabled": False,
    "screenshot_retention_days": 7,
    # Empty = default under AppData\Local\Deskline\screenshots
    "screenshots_dir": "",
    "open_dashboard_on_start": False,
    "autostart": False,
    "paused": False,
    # Compact always-on-top widget (Time Doctor-style)
    "show_mini_tracker": True,
    # UI theme: system | light | dark
    "theme": "system",
    # When True, messaging activities count as productive (unless user override)
    "work_mode": False,
    # Title substrings → force productive (work chats)
    "work_chat_keywords": [],
    "current_project_id": None,
    "current_task_id": None,
    # Company / LAN hub
    "company_mode": False,
    "company_display_name": "",
    "listen_host": "127.0.0.1",
    "local_employee_id": None,
    # Agent → hub push (member PC)
    "hub_url": "",
    "hub_ingest_token": "",
    # Freemium / trial
    "first_run_at": "",
    "onboarding_done": False,
    # Pro RDP vision (opt-in; never on by default)
    "rdp_vision_enabled": False,
    "rdp_vision_consent": False,
    "rdp_vision_api_key": "",
    "rdp_vision_interval_sec": 180,
    "rdp_vision_base_url": "https://api.openai.com/v1",
    "rdp_vision_model": "gpt-4o-mini",
}


def ensure_data_dirs() -> None:
    DATA_ROOT.mkdir(parents=True, exist_ok=True)
    SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)
    ICONS_DIR.mkdir(parents=True, exist_ok=True)


def get_screenshots_dir(cfg: dict[str, Any] | None = None) -> Path:
    """Return configured screenshots folder, or the default under DATA_ROOT."""
    data = cfg if cfg is not None else _read_raw_config()
    custom = str(data.get("screenshots_dir") or "").strip()
    if custom:
        return Path(custom).expanduser()
    return SCREENSHOTS_DIR


def ensure_screenshots_dir(cfg: dict[str, Any] | None = None) -> Path:
    path = get_screenshots_dir(cfg)
    path.mkdir(parents=True, exist_ok=True)
    return path


def _read_raw_config() -> dict[str, Any]:
    cfg = deepcopy(DEFAULT_CONFIG)
    if CONFIG_PATH.exists():
        try:
            raw = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                cfg.update({k: raw[k] for k in DEFAULT_CONFIG if k in raw})
        except (OSError, json.JSONDecodeError):
            pass
    return cfg


def _normalize_config(cfg: dict[str, Any]) -> dict[str, Any]:
    merged = deepcopy(DEFAULT_CONFIG)
    merged.update({k: cfg[k] for k in DEFAULT_CONFIG if k in cfg})
    try:
        interval = int(merged.get("screenshot_interval_sec", 300))
    except (TypeError, ValueError):
        interval = 300
    merged["screenshot_interval_sec"] = max(60, min(3600, interval))
    custom = str(merged.get("screenshots_dir") or "").strip()
    merged["screenshots_dir"] = custom
    return merged


def load_config() -> dict[str, Any]:
    ensure_data_dirs()
    cfg = _normalize_config(_read_raw_config())
    ensure_screenshots_dir(cfg)
    return cfg


def save_config(cfg: dict[str, Any]) -> dict[str, Any]:
    ensure_data_dirs()
    merged = _normalize_config(cfg)
    ensure_screenshots_dir(merged)
    CONFIG_PATH.write_text(json.dumps(merged, indent=2), encoding="utf-8")
    return merged


def brand_template_context(*, version: str | None = None, base_url: str | None = None) -> dict[str, Any]:
    """Shared Jinja context for dashboard and legal pages."""
    from datetime import datetime

    from deskline import __version__

    return {
        "app_name": APP_NAME,
        "version": version or __version__,
        "base_url": base_url if base_url is not None else BASE_URL,
        "company_name": COMPANY_NAME,
        "support_email": SUPPORT_EMAIL,
        "github_url": GITHUB_URL,
        "github_releases_url": GITHUB_RELEASES_URL,
        "download_setup_url": f"{GITHUB_URL}/releases/latest",
        "privacy_policy_url": f"{GITHUB_URL}/blob/master/docs/PRIVACY_POLICY.md",
        "legal_jurisdiction": LEGAL_JURISDICTION,
        "copyright_year": datetime.now().astimezone().year,
    }
