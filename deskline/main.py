from __future__ import annotations

import argparse
import signal
import sys
import threading
from pathlib import Path

import uvicorn

from deskline.api import create_app, open_dashboard
from deskline.config import DATA_ROOT, HOST, PORT, ensure_data_dirs, load_config
from deskline.db import Database
from deskline.tracker import Tracker
from deskline.tray import start_tray


def _ensure_stdio() -> Path | None:
    """PyInstaller windowed builds leave stdout/stderr as None — break uvicorn logging."""
    ensure_data_dirs()
    log_path = DATA_ROOT / "deskline.log"
    if sys.stdout is None or sys.stderr is None:
        log_file = open(log_path, "a", encoding="utf-8", buffering=1)  # noqa: SIM115
        if sys.stdout is None:
            sys.stdout = log_file
        if sys.stderr is None:
            sys.stderr = log_file
        return log_path
    return None


def _uvicorn_log_config() -> dict:
    """Plain formatters that do not call stream.isatty()."""
    return {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "default": {
                "format": "%(asctime)s %(levelname)s %(name)s: %(message)s",
            },
            "access": {
                "format": '%(asctime)s %(levelname)s %(client_addr)s - "%(request_line)s" %(status_code)s',
            },
        },
        "handlers": {
            "default": {
                "formatter": "default",
                "class": "logging.StreamHandler",
                "stream": "ext://sys.stderr",
            },
            "access": {
                "formatter": "access",
                "class": "logging.StreamHandler",
                "stream": "ext://sys.stdout",
            },
        },
        "loggers": {
            "uvicorn": {"handlers": ["default"], "level": "INFO", "propagate": False},
            "uvicorn.error": {"handlers": ["default"], "level": "INFO", "propagate": False},
            "uvicorn.access": {"handlers": ["access"], "level": "INFO", "propagate": False},
        },
    }


def main(argv: list[str] | None = None) -> int:
    _ensure_stdio()

    parser = argparse.ArgumentParser(description="Deskline local productivity tracker")
    parser.add_argument("--no-browser", action="store_true", help="Do not open the dashboard")
    parser.add_argument("--no-tray", action="store_true", help="Run without system tray icon")
    parser.add_argument("--host", default=HOST)
    parser.add_argument("--port", type=int, default=PORT)
    args = parser.parse_args(argv)

    ensure_data_dirs()
    db = Database()
    tracker = Tracker(db)
    tracker.start()

    app = create_app(tracker, db)
    config = uvicorn.Config(
        app,
        host=args.host,
        port=args.port,
        log_level="info",
        access_log=False,
        log_config=_uvicorn_log_config(),
    )
    server = uvicorn.Server(config)

    stop_event = threading.Event()

    def shutdown() -> None:
        if stop_event.is_set():
            return
        stop_event.set()
        tracker.stop()
        server.should_exit = True

    def handle_signal(_sig: int, _frame: object) -> None:
        shutdown()

    signal.signal(signal.SIGINT, handle_signal)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, handle_signal)

    if not args.no_tray:
        try:
            start_tray(
                get_status=tracker.status,
                on_pause=tracker.pause,
                on_resume=tracker.resume,
                on_open=open_dashboard,
                on_quit=shutdown,
            )
        except Exception as exc:  # noqa: BLE001
            print(f"Tray unavailable, continuing without it: {exc}", file=sys.stderr)

    cfg = load_config()
    if cfg.get("open_dashboard_on_start") and not args.no_browser:
        threading.Timer(1.0, open_dashboard).start()

    try:
        server.run()
    finally:
        tracker.stop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
