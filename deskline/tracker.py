from __future__ import annotations

import threading
import time
from datetime import datetime
from typing import Callable

from deskline.capture import capture_screenshot
from deskline.classify import extract_site_from_title, is_rdp_client, normalize_category, resolve_activity
from deskline.config import load_config, save_config
from deskline.db import Database, parse_iso_datetime
from deskline.heartbeat import clear_heartbeat, load_heartbeat, save_heartbeat
from deskline.hub_client import push_sessions_to_hub
from deskline.idle import is_idle, seconds_since_last_input
from deskline.notify import ask_still_working, notify, still_working_body
from deskline.power import DEFAULT_SLEEP_GAP_SEC, is_sleep_gap, system_boot_time
from deskline.windows import get_active_window


def _shots_allowed(cfg: dict) -> bool:
    try:
        from deskline.entitlements import resolve_entitlements
        from deskline.license_store import load_license

        return resolve_entitlements(cfg, load_license()).screenshots
    except Exception:
        return False


def _is_pro(cfg: dict) -> bool:
    try:
        from deskline.entitlements import resolve_entitlements
        from deskline.license_store import load_license

        return resolve_entitlements(cfg, load_license()).is_pro
    except Exception:
        return False


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
        self._current_app_path: str | None = None
        self._rdp_vision_label: str | None = None
        self._distracting_since: float | None = None
        self._last_poor_notify: dict[str, float] = {}
        self._still_working_prompting = False
        self._suppress_still_working_until = 0.0
        self._idle_since: float | None = None
        self._last_screenshot_at = 0.0
        self._last_purge_at = 0.0
        self._last_tick_at = time.time()
        self._idle = False
        self._status_listeners: list[Callable[[dict], None]] = []
        self._session_started_at: float | None = None
        self.cfg = load_config()

        # Hard power-off / kill leaves ended_at NULL; never resume across restarts.
        self._reclaim_orphan_sessions()
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
            meta = resolve_activity(
                current_app,
                current_title,
                work_mode=bool(self.cfg.get("work_mode")),
                work_chat_keywords=list(self.cfg.get("work_chat_keywords") or []),
            )
            label = meta.get("activity_label") or meta.get("display_name")
        project_id = self.cfg.get("current_project_id")
        task_id = self.cfg.get("current_task_id")
        try:
            project_id = int(project_id) if project_id is not None else None
        except (TypeError, ValueError):
            project_id = None
        try:
            task_id = int(task_id) if task_id is not None else None
        except (TypeError, ValueError):
            task_id = None
        project = self.db.get_project(project_id)
        task = self.db.get_task(task_id)
        elapsed = 0.0
        if self._session_started_at and not self.paused:
            elapsed = max(0.0, time.time() - self._session_started_at)
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
            "work_mode": bool(self.cfg.get("work_mode")),
            "current_project_id": project_id,
            "current_task_id": task_id,
            "project_name": (project or {}).get("name") or "",
            "task_name": (task or {}).get("name") or "",
            "session_elapsed_sec": round(elapsed, 1),
            "show_mini_tracker": bool(self.cfg.get("show_mini_tracker", True)),
            "rdp_vision_pending": self._rdp_pending_public(),
        }

    def _rdp_pending_public(self) -> dict | None:
        try:
            from deskline import rdp_vision

            return rdp_vision.get_pending()
        except Exception:
            return None

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
            # Reload from disk first so pause cannot overwrite fresher settings
            # (e.g. screenshot_interval_sec) with a stale in-memory copy.
            cfg = load_config()
            cfg["paused"] = True
            self.cfg = save_config(cfg)
            self._close_current_unlocked()
            self._idle = False
            self._idle_since = None
            self._distracting_since = None
            self._still_working_prompting = False
        self._emit()

    def resume(self) -> None:
        with self._lock:
            cfg = load_config()
            cfg["paused"] = False
            self.cfg = save_config(cfg)
            self._last_tick_at = time.time()
            self._idle_since = None
            self._still_working_prompting = False
            self._suppress_still_working_until = 0.0
        self._emit()

    def reload_config(self) -> None:
        with self._lock:
            self.cfg = load_config()
        self.purge_old_screenshots()

    def apply_focus(self) -> None:
        """Reload config and split the open session so new project/task apply immediately."""
        with self._lock:
            self.cfg = load_config()
            self._close_current_unlocked()
        self._emit()

    def purge_old_screenshots(self) -> dict:
        days = int(self.cfg.get("screenshot_retention_days", 7))
        result = self.db.purge_old_screenshots(days)
        self._last_purge_at = time.time()
        return result

    def _reclaim_orphan_sessions(self) -> None:
        """Close sessions left open across hard power-off / process kill.

        Sleep gaps only work while the process stays alive. Battery death kills
        the process with ended_at NULL; resuming that row until "now" invents
        overnight focus (solid green from 00:00).

        Never resume an open row across process restarts — close at the last
        heartbeat (or started_at if none) and let the next tick open a fresh one.
        """
        boot = system_boot_time()
        try:
            self.db.repair_sessions_spanning_boot(boot)
        except Exception:
            pass
        try:
            self.db.repair_phantom_overnight_sessions()
        except Exception:
            pass

        open_sess = self.db.open_session()
        if not open_sess:
            clear_heartbeat()
            return

        try:
            started = parse_iso_datetime(open_sess.started_at).timestamp()
        except Exception:
            started = time.time()

        hb = load_heartbeat()
        if hb and int(hb["session_id"]) == int(open_sess.id):
            end_ts = max(float(hb["last_tick_at"]), started)
        else:
            end_ts = started

        ended = datetime.fromtimestamp(end_ts).astimezone()
        self.db.end_session(open_sess.id, ended_at=ended)
        clear_heartbeat()

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
            prev_tick = self._last_tick_at
            dt = max(0.0, now - prev_tick)
            self._last_tick_at = now

            if cfg.get("paused"):
                self._idle = False
                self._idle_since = None
                return

            sleep_gap = float(cfg.get("sleep_gap_sec", DEFAULT_SLEEP_GAP_SEC))
            if is_sleep_gap(dt, sleep_gap):
                self._handle_sleep_wake(prev_tick, now)
                # Continue into normal tick so a fresh session starts after wake

            if self._current_session_id is not None:
                save_heartbeat(self._current_session_id, now)

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
            switched = self._current_key != key or self._current_session_id is None

            # Only accrue idle for small real-time gaps (never sleep wall-clock)
            poll = float(cfg.get("poll_interval_sec", 2.0))
            idle_dt = min(dt, poll * 3) if not is_sleep_gap(dt, sleep_gap) else 0.0
            if (
                not switched
                and self._current_session_id is not None
                and self._idle
                and idle_dt > 0
            ):
                self.db.add_idle_seconds(self._current_session_id, idle_dt)

            if switched:
                self._close_current_unlocked()
                site = extract_site_from_title(win.window_title, win.app_name)
                meta = resolve_activity(
                    win.app_name,
                    win.window_title,
                    site,
                    self.db.get_app_rules(),
                    self.db.get_site_rules(),
                    work_mode=bool(cfg.get("work_mode")),
                    work_chat_keywords=list(cfg.get("work_chat_keywords") or []),
                )
                project_id = cfg.get("current_project_id")
                task_id = cfg.get("current_task_id")
                try:
                    project_id = int(project_id) if project_id is not None else None
                except (TypeError, ValueError):
                    project_id = None
                try:
                    task_id = int(task_id) if task_id is not None else None
                except (TypeError, ValueError):
                    task_id = None
                employee_id = cfg.get("local_employee_id")
                try:
                    employee_id = int(employee_id) if employee_id is not None else None
                except (TypeError, ValueError):
                    employee_id = None
                if employee_id is None:
                    employee_id = self.db.ensure_default_employee()
                    cfg["local_employee_id"] = employee_id
                    save_config(cfg)
                import socket

                hostname = socket.gethostname() or "pc"
                ingest_key = f"{hostname}:local:{int(now * 1000)}"
                self._current_session_id = self.db.start_session(
                    app_name=win.app_name,
                    window_title=win.window_title,
                    url_hint=meta.get("url_hint") or site,
                    category=meta["category"],
                    display_name=meta["display_name"],
                    activity_kind=meta["activity_kind"],
                    activity_label=meta["activity_label"],
                    app_path=win.app_path,
                    project_id=project_id,
                    task_id=task_id,
                    employee_id=employee_id,
                    ingest_key=ingest_key,
                    started_at=datetime.fromtimestamp(now).astimezone(),
                )
                self._session_started_at = now
                save_heartbeat(self._current_session_id, now)
                try:
                    from deskline.icons import ensure_app_icon, ensure_site_icon

                    ensure_app_icon(win.app_name, win.app_path)
                    hint = meta.get("url_hint") or site
                    if hint:
                        ensure_site_icon(hint)
                except Exception:
                    pass
                self._current_key = key
                self._current_app_path = win.app_path
                self._current_category = normalize_category(meta["category"])
                self._current_label = meta.get("activity_label") or meta.get("display_name")
                if not is_rdp_client(win.app_name):
                    self._rdp_vision_label = None
                elif self._rdp_vision_label:
                    # Keep confirmed remote label on same RDP host session
                    self._current_label = self._rdp_vision_label
                    try:
                        self.db.update_session_activity(
                            self._current_session_id,
                            activity_label=self._rdp_vision_label,
                            activity_kind="remote",
                        )
                    except Exception:
                        pass
                self._distracting_since = (
                    now if self._current_category == "distracting" else None
                )
                if (
                    _shots_allowed(cfg)
                    and cfg.get("screenshots_enabled")
                    and cfg.get("screenshot_on_app_switch")
                ):
                    self._shot_unlocked("app_switch")
                    self._last_screenshot_at = now
            else:
                if self._current_category == "distracting":
                    if self._distracting_since is None:
                        self._distracting_since = now
                else:
                    self._distracting_since = None

                if (
                    _shots_allowed(cfg)
                    and cfg.get("screenshots_enabled")
                    and self._current_session_id
                    and not self._idle
                    and (now - self._last_screenshot_at)
                    >= float(cfg.get("screenshot_interval_sec", 300))
                ):
                    self._shot_unlocked("interval")
                    self._last_screenshot_at = now

            self._maybe_rdp_vision(cfg, win.app_name, win.window_title)
            self._maybe_poor_time(cfg, now)
            self._maybe_still_working(cfg, now)

        self._emit()

    def _maybe_rdp_vision(self, cfg: dict, app_name: str | None, window_title: str | None) -> None:
        if self._idle or self.paused:
            return
        if not is_rdp_client(app_name):
            return
        if self._rdp_vision_label:
            return  # already confirmed for this stretch
        if getattr(self, "_rdp_vision_thread", None) and self._rdp_vision_thread.is_alive():
            return
        from deskline import rdp_vision

        if not rdp_vision.vision_enabled(cfg, is_pro=_is_pro(cfg)):
            return
        if rdp_vision.get_pending():
            return

        def worker() -> None:
            try:
                from deskline.classify import parse_rdp_host

                rdp_vision.maybe_analyze_rdp(
                    cfg,
                    app_name=app_name,
                    is_pro=_is_pro(cfg),
                    session_id=self._current_session_id,
                    host_hint=parse_rdp_host(window_title),
                )
                self._emit()
            except Exception:
                pass

        self._rdp_vision_thread = threading.Thread(
            target=worker, name="deskline-rdp-vision", daemon=True
        )
        self._rdp_vision_thread.start()

    def apply_rdp_vision_label(self, label: str, session_id: int | None = None) -> bool:
        """Confirm a vision suggestion: relabel session; focus % still from local categories."""
        text = (label or "").strip()
        if not text:
            return False
        sid = session_id or self._current_session_id
        if not sid:
            return False
        ok = self.db.update_session_activity(
            sid, activity_label=text, activity_kind="remote"
        )
        if ok:
            self._rdp_vision_label = text
            if sid == self._current_session_id:
                self._current_label = text
            self._emit()
        return ok

    def _handle_sleep_wake(self, prev_tick: float, now: float) -> None:
        """Close session at last awake moment; reset idle/prompt state. Do not pause."""
        if self._current_session_id is not None:
            ended = datetime.fromtimestamp(prev_tick).astimezone()
            sid = self._current_session_id
            self.db.end_session(sid, ended_at=ended)
            self._push_session_to_hub(sid)
            clear_heartbeat()
            self._current_session_id = None
        self._session_started_at = None
        # Force a new session on the next focus sample
        self._current_key = None
        self._idle = False
        self._idle_since = None
        self._distracting_since = None
        self._still_working_prompting = False
        # Suppress still-working prompt after wake (user just returned)
        self._suppress_still_working_until = now + 300.0

    def _maybe_poor_time(self, cfg: dict, now: float) -> None:
        if not cfg.get("poor_time_popup", True):
            return
        if not cfg.get("work_mode"):
            return
        if self._current_category != "distracting" or self._distracting_since is None:
            return
        min_sec = float(cfg.get("poor_time_min_sec", 60.0))
        held = now - self._distracting_since
        if held < min_sec:
            return
        label = self._current_label or (self._current_key[0] if self._current_key else "app")
        last = self._last_poor_notify.get(label, 0.0)
        if now - last < 600:
            return
        self._last_poor_notify[label] = now
        mins = max(1, int(held // 60))
        notify("Отвлечение", f"{label} — уже {mins} мин")

    def _maybe_still_working(self, cfg: dict, now: float) -> None:
        if not self._idle or self._idle_since is None:
            return
        if self._still_working_prompting or self.paused:
            return
        if now < self._suppress_still_working_until:
            return
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
        notify("Deskline", "Давно нет ввода — вы ещё за компьютером?")
        answer = ask_still_working(
            "Deskline",
            still_working_body(label),
            timeout_sec=45.0,
        )
        with self._lock:
            self._still_working_prompting = False
            if answer in ("yes", "timeout"):
                self._idle_since = None
                self._idle = False
                pause_now = False
            else:
                pause_now = True
        if pause_now:
            self.pause()
            notify("Deskline", "Трекинг на паузе")
        else:
            notify("Deskline", "Трекинг продолжается")

    def _shot_unlocked(self, reason: str) -> None:
        path = capture_screenshot(prefix="deskline")
        self.db.add_screenshot(str(path), reason=reason, session_id=self._current_session_id)

    def _close_current(self) -> None:
        with self._lock:
            self._close_current_unlocked()

    def _close_current_unlocked(self) -> None:
        if self._current_session_id is not None:
            sid = self._current_session_id
            self.db.end_session(sid)
            self._push_session_to_hub(sid)
            clear_heartbeat()
        self._current_session_id = None
        self._session_started_at = None
        self._current_key = None
        self._current_label = None
        self._current_app_path = None
        self._distracting_since = None

    def _push_session_to_hub(self, session_id: int) -> None:
        cfg = load_config()
        hub_url = str(cfg.get("hub_url") or "").strip()
        token = str(cfg.get("hub_ingest_token") or "").strip()
        if not hub_url or not token:
            return
        payload = self.db.get_session_payload(session_id)
        if not payload or not payload.get("ended_at"):
            return
        if not payload.get("ingest_key"):
            import socket

            payload["ingest_key"] = f"{socket.gethostname()}:local:{session_id}"
        threading.Thread(
            target=push_sessions_to_hub,
            args=(hub_url, token, [payload]),
            daemon=True,
            name="deskline-hub-push",
        ).start()
