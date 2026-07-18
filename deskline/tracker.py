from __future__ import annotations

import threading
import time
from typing import Callable

from deskline.capture import capture_screenshot
from deskline.classify import classify, extract_site_from_title
from deskline.config import load_config, save_config
from deskline.db import Database
from deskline.windows import get_active_window


class Tracker:
    def __init__(self, db: Database | None = None) -> None:
        self.db = db or Database()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()
        self._current_key: tuple[str, str] | None = None
        self._current_session_id: int | None = None
        self._last_screenshot_at = 0.0
        self._status_listeners: list[Callable[[dict], None]] = []
        self.cfg = load_config()

        open_sess = self.db.open_session()
        if open_sess:
            self._current_session_id = open_sess.id
            self._current_key = (open_sess.app_name, open_sess.window_title)

    @property
    def paused(self) -> bool:
        return bool(self.cfg.get("paused"))

    def on_status(self, cb: Callable[[dict], None]) -> None:
        self._status_listeners.append(cb)

    def status(self) -> dict:
        return {
            "paused": self.paused,
            "recording": not self.paused and self._thread is not None and self._thread.is_alive(),
            "current_session_id": self._current_session_id,
            "current_app": self._current_key[0] if self._current_key else None,
            "current_title": self._current_key[1] if self._current_key else None,
        }

    def _emit(self) -> None:
        st = self.status()
        for cb in list(self._status_listeners):
            try:
                cb(st)
            except Exception:
                pass

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, name="deskline-tracker", daemon=True)
        self._thread.start()
        self._emit()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=5)
        self._close_current()
        self._emit()

    def pause(self) -> None:
        with self._lock:
            self.cfg["paused"] = True
            save_config(self.cfg)
            self._close_current()
        self._emit()

    def resume(self) -> None:
        with self._lock:
            self.cfg["paused"] = False
            save_config(self.cfg)
        self._emit()

    def reload_config(self) -> None:
        with self._lock:
            self.cfg = load_config()

    def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                self._tick()
            except Exception:
                pass
            interval = float(self.cfg.get("poll_interval_sec", 2.0))
            self._stop.wait(interval)

    def _tick(self) -> None:
        with self._lock:
            cfg = dict(self.cfg)
            if cfg.get("paused"):
                return

            win = get_active_window()
            if not win:
                return

            key = (win.app_name, win.window_title)
            now = time.time()
            switched = self._current_key != key

            if switched:
                self._close_current_unlocked()
                site = extract_site_from_title(win.window_title, win.app_name)
                category = classify(
                    win.app_name,
                    site,
                    self.db.get_app_rules(),
                    self.db.get_site_rules(),
                )
                self._current_session_id = self.db.start_session(
                    app_name=win.app_name,
                    window_title=win.window_title,
                    url_hint=site,
                    category=category,
                )
                self._current_key = key
                if cfg.get("screenshots_enabled") and cfg.get("screenshot_on_app_switch"):
                    self._shot_unlocked("app_switch")
                    self._last_screenshot_at = now
            elif (
                cfg.get("screenshots_enabled")
                and self._current_session_id
                and (now - self._last_screenshot_at) >= float(cfg.get("screenshot_interval_sec", 300))
            ):
                self._shot_unlocked("interval")
                self._last_screenshot_at = now

        self._emit()

    def _shot_unlocked(self, reason: str) -> None:
        path = capture_screenshot(prefix="deskline")
        self.db.add_screenshot(str(path), reason=reason, session_id=self._current_session_id)

    def _close_current(self) -> None:
        with self._lock:
            self._close_current_unlocked()

    def _close_current_unlocked(self) -> None:
        if self._current_session_id is not None:
            self.db.end_session(self._current_session_id)
        self._current_session_id = None
        self._current_key = None
