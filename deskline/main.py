from __future__ import annotations

import argparse
import signal
import threading

import uvicorn

from deskline.api import create_app, open_dashboard
from deskline.config import HOST, PORT, ensure_data_dirs, load_config
from deskline.db import Database
from deskline.tracker import Tracker
from deskline.tray import start_tray


def main(argv: list[str] | None = None) -> int:
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
    config = uvicorn.Config(app, host=args.host, port=args.port, log_level="info", access_log=False)
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
        start_tray(
            get_status=tracker.status,
            on_pause=tracker.pause,
            on_resume=tracker.resume,
            on_open=open_dashboard,
            on_quit=shutdown,
        )

    cfg = load_config()
    if cfg.get("open_dashboard_on_start") and not args.no_browser:
        threading.Timer(1.0, open_dashboard).start()

    # Run uvicorn in main thread
    try:
        server.run()
    finally:
        tracker.stop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
