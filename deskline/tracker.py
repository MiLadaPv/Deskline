from __future__ import annotations

import threading
import time
from typing import Callable

from deskline.capture import capture_screenshot
from deskline.classify import extract_site_from_title, normalize_category, resolve_activity
from deskline.config import load_config, save_config
from deskline.db import Database
from deskline.idle import is_idle, seconds_since_last_input
from deskline.notify import ask_yes_no, notify
from deskline.windows import get_active_window


class Tracker:
    def __init__(self, db: Database | None = None) -> None:
        self.db = db or Database()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()
        self._current_key: tuple[str, str] | None = None
        self._current_session_id: int | None = None
        self._current_category: str = "neutral"
        self._current_label: str | None = None
        self._distracting_since: float | None = None
        self._last_poor_notify: dict[str, float] = {}
        self._still_working_prompting = False
        self._idle_since: float | None = None
        self._last_screenshot_at = 0.0
        self._last_purge_at = 0.0
        self._last_tick_at = time.time()
        self._idle = False
        self._status_listeners: list[Callable[[dict], None]] = []
        self.cfg = load_config()

        open_sess = self.db.open_session()
        if open_sess:
            self._current_session_id = open_sess.id
            self._current_key = (open_sess.app_name, open_sess.window_title)
            self._current_category = normalize_category(open_sess.category)
            self._current_label = open_sess.activity_label or open_sess.display_name
        self.purge_old_screenshots()

    @property
    def paused(self) -> bool:
        return bool(self.cfg.get("paused"))

    def on_status(self, cb: Callable[[dict], None]) -> None:
        self._status_listeners.append(cb)

    def status(self) -> dict:
        current_app = self._current_key[0] if self._current_key else None
        current_title = self._current_key[1] if self._current_key else None
        label = self._current_label
        if current_app and not label:
            meta = resolve_activity(current_app, current_title)
            label = meta.get("activity_label") or meta.get("display_name")
        return {
            "paused": self.paused,
            "recording": not self.paused and self._thread is not None and self._thread.is_alive(),
            "current_session_id": self._current_session_id,
            "current_app": current_app,
            "current_title": current_title,
            "current_label": label,
            "current_category": self._current_category,
            "idle": self._idle,
            "idle_for_sec": round(seconds_since_last_input(), 1),
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
        self._last_tick_at = time.time()
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
            self._close_current_unlocked()
            self._idle = False
            self._idle_since = None
            self._distracting_since = None
            self._still_working_prompting = False
        self._emit()

    def resume(self) -> None:
        with self._lock:
            self.cfg["paused"] = False
            save_config(self.cfg)
            self._last_tick_at = time.time()
            self._idle_since = None
            self._still_working_prompting = False
        self._emit()

    def reload_config(self) -> None:
        with self._lock:
            self.cfg = load_config()
        self.purge_old_screenshots()

    def purge_old_screenshots(self) -> dict:
        days = int(self.cfg.get("screenshot_retention_days", 7))
        result = self.db.purge_old_screenshots(days)
        self._last_purge_at = time.time()
        return result

    def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                self._tick()
                now = time.time()
                if now - self._last_purge_at >= 3600:
                    self.purge_old_screenshots()
            except Exception:
                pass
            interval = float(self.cfg.get("poll_interval_sec", 2.0))
            self._stop.wait(interval)

    def _tick(self) -> None:
        with self._lock:
            cfg = dict(self.cfg)
            now = time.time()
            dt = max(0.0, now - self._last_tick_at)
            self._last_tick_at = now

            if cfg.get("paused"):
                self._idle = False
                self._idle_since = None
                return

            win = get_active_window()
            if not win:
                return

            idle_after = float(cfg.get("idle_after_sec", 180.0))
            self._idle = is_idle(idle_after, win.app_name)
            if self._idle:
                if self._idle_since is None:
                    self._idle_since = now
            else:
                self._idle_since = None
                self._still_working_prompting = False

            key = (win.app_name, win.window_title)
            switched = self._current_key != key

            if (
                not switched
                and self._current_session_id is not None
                and self._idle
                and dt > 0
            ):
                self.db.add_idle_seconds(self._current_session_id, dt)

            if switched:
                self._close_current_unlocked()
                site = extract_site_from_title(win.window_title, win.app_name)
                meta = resolve_activity(
                    win.app_name,
                    win.window_title,
                    site,
                    self.db.get_app_rules(),
                    self.db.get_site_rules(),
                )
                self._current_session_id = self.db.start_session(
                    app_name=win.app_name,
                    window_title=win.window_title,
                    url_hint=meta.get("url_hint") or site,
                    category=meta["category"],
                    display_name=meta["display_name"],
                    activity_kind=meta["activity_kind"],
                    activity_label=meta["activity_label"],
                    app_path=win.app_path,
                )
                try:
                    from deskline.icons import ensure_app_icon

                    ensure_app_icon(win.app_name, win.app_path)
                except Exception:
                    pass
                self._current_key = key
                self._current_category = normalize_category(meta["category"])
                self._current_label = meta.get("activity_label") or meta.get("display_name")
                self._distracting_since = (
                    now if self._current_category == "distracting" else None
                )
                if cfg.get("screenshots_enabled") and cfg.get("screenshot_on_app_switch"):
                    self._shot_unlocked("app_switch")
                    self._last_screenshot_at = now
            else:
                if self._current_category == "distracting":
                    if self._distracting_since is None:
                        self._distracting_since = now
                else:
                    self._distracting_since = None

                if (
                    cfg.get("screenshots_enabled")
                    and self._current_session_id
                    and not self._idle
                    and (now - self._last_screenshot_at)
                    >= float(cfg.get("screenshot_interval_sec", 300))
                ):
                    self._shot_unlocked("interval")
                    self._last_screenshot_at = now

            self._maybe_poor_time(cfg, now)
            self._maybe_still_working(cfg, now)

        self._emit()

    def _maybe_poor_time(self, cfg: dict, now: float) -> None:
        if not cfg.get("poor_time_popup", True):
            return
        if self._current_category != "distracting" or self._distracting_since is None:
            return
        min_sec = float(cfg.get("poor_time_min_sec", 60.0))
        held = now - self._distracting_since
        if held < min_sec:
            return
        label = self._current_label or (self._current_key[0] if self._current_key else "app")
        last = self._last_poor_notify.get(label, 0.0)
        if now - last < 600:  # at most once per 10 min per label
            return
        self._last_poor_notify[label] = now
        mins = max(1, int(held // 60))
        notify("Отвлечение", f"{label} — уже {mins} мин")

    def _maybe_still_working(self, cfg: dict, now: float) -> None:
        if not self._idle or self._idle_since is None:
            return
        if self._still_working_prompting or self.paused:
            return
        # is_idle() already waited idle_after_sec; grace starts when idle was detected
        grace = float(cfg.get("still_working_grace_sec", 60.0))
        if now - self._idle_since < grace:
            return
        self._still_working_prompting = True
        label = self._current_label or "Deskline"
        threading.Thread(
            target=self._ask_still_working,
            args=(label,),
            name="deskline-still-working",
            daemon=True,
        ).start()

    def _ask_still_working(self, label: str) -> None:
        notify("Deskline", "Давно нет ввода — вы ещё работаете?")
        yes = ask_yes_no(
            "Deskline",
            f"Нет ввода уже некоторое время ({label}).\n\nВы ещё работаете?",
        )
        with self._lock:
            self._still_working_prompting = False
            if yes:
                self._idle_since = None
                self._idle = False
            else:
                # release lock before pause (pause takes lock)
                pass
        if not yes:
            self.pause()
            notify("Deskline", "Трекинг на паузе")

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
        self._current_label = None
        self._distracting_since = None
