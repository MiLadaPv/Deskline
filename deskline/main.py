from __future__ import annotations

import argparse
import ctypes
import signal
import socket
import sys
import threading
from pathlib import Path

import uvicorn

from deskline.api import create_app, open_dashboard
from deskline.config import DATA_ROOT, HOST, PORT, ensure_data_dirs, load_config
from deskline.db import Database
from deskline.icons import purge_placeholder_icons
from deskline.mini_tracker import MiniTracker
from deskline.tracker import Tracker
from deskline.tray import start_tray

_MUTEX_NAME = "Local\\DesklineSingleInstance"
_ERROR_ALREADY_EXISTS = 183


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


def _port_open(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout=0.4):
            return True
    except OSError:
        return False


def _try_acquire_instance_lock() -> int | None:
    """Return a mutex handle if we are the primary instance, else None."""
    try:
        handle = ctypes.windll.kernel32.CreateMutexW(None, False, _MUTEX_NAME)
    except Exception:
        return -1  # lock unavailable — allow start
    if not handle:
        return -1
    if ctypes.windll.kernel32.GetLastError() == _ERROR_ALREADY_EXISTS:
        ctypes.windll.kernel32.CloseHandle(handle)
        return None
    return int(handle)


def _release_instance_lock(handle: int | None) -> None:
    if handle is None or handle == -1:
        return
    try:
        ctypes.windll.kernel32.CloseHandle(handle)
    except Exception:
        pass


def _handoff_to_running_instance(*, open_browser: bool, reason: str) -> int:
    if open_browser:
        open_dashboard()
    print(f"Deskline already running ({reason}) — opened dashboard.", file=sys.stderr)
    return 0


def main(argv: list[str] | None = None) -> int:
    _ensure_stdio()

    parser = argparse.ArgumentParser(description="Deskline local productivity tracker")
    parser.add_argument("--no-browser", action="store_true", help="Do not open the dashboard")
    parser.add_argument("--no-tray", action="store_true", help="Run without system tray icon")
    parser.add_argument("--host", default=HOST)
    parser.add_argument("--port", type=int, default=PORT)
    parser.add_argument(
        "--allow-duplicate",
        action="store_true",
        help="Skip single-instance lock (tests / diagnostics only)",
    )
    args = parser.parse_args(argv)
    open_browser = not args.no_browser

    mutex_handle: int | None = -1
    if not args.allow_duplicate:
        mutex_handle = _try_acquire_instance_lock()
        if mutex_handle is None:
            return _handoff_to_running_instance(open_browser=open_browser, reason="mutex")
        if _port_open(args.host, args.port):
            _release_instance_lock(mutex_handle)
            return _handoff_to_running_instance(open_browser=open_browser, reason="port")

    ensure_data_dirs()
    purge_placeholder_icons()
    db = Database()
    tracker = Tracker(db)
    tracker.start()

    mini = MiniTracker(
        get_snapshot=tracker.status,
        on_pause=tracker.pause,
        on_resume=tracker.resume,
        on_open=open_dashboard,
    )
    try:
        mini.start()
    except Exception as exc:  # noqa: BLE001
        print(f"Mini tracker unavailable: {exc}", file=sys.stderr)

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
        mini.stop()
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
                on_show_mini=mini.show,
            )
        except Exception as exc:  # noqa: BLE001
            print(f"Tray unavailable, continuing without it: {exc}", file=sys.stderr)

    cfg = load_config()
    if cfg.get("open_dashboard_on_start") and open_browser:
        threading.Timer(1.0, open_dashboard).start()

    try:
        server.run()
    finally:
        mini.stop()
        tracker.stop()
        _release_instance_lock(mutex_handle)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
