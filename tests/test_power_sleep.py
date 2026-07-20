from __future__ import annotations

import time
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock

from deskline.db import Database
from deskline.power import DEFAULT_SLEEP_GAP_SEC, is_sleep_gap
from deskline.tracker import Tracker
from deskline.windows import ActiveWindow


def test_is_sleep_gap_threshold():
    assert not is_sleep_gap(0)
    assert not is_sleep_gap(119, 120)
    assert is_sleep_gap(120, 120)
    assert is_sleep_gap(1800, DEFAULT_SLEEP_GAP_SEC)


def test_sleep_wake_closes_session_without_pause_or_prompt(tmp_path: Path, monkeypatch):
    data = tmp_path / "Deskline"
    monkeypatch.setattr("deskline.config.DATA_ROOT", data)
    monkeypatch.setattr("deskline.config.DB_PATH", data / "deskline.db")
    monkeypatch.setattr("deskline.config.SCREENSHOTS_DIR", data / "screenshots")
    monkeypatch.setattr("deskline.config.ICONS_DIR", data / "icons")
    monkeypatch.setattr("deskline.config.CONFIG_PATH", data / "config.json")
    data.mkdir(parents=True)
    (data / "screenshots").mkdir()
    (data / "icons").mkdir()

    db = Database(data / "deskline.db")
    tracker = Tracker(db)
    tracker.cfg = {
        **tracker.cfg,
        "paused": False,
        "sleep_gap_sec": 120.0,
        "poll_interval_sec": 2.0,
        "idle_after_sec": 180.0,
        "screenshots_enabled": False,
        "poor_time_popup": False,
        "work_mode": False,
        "work_chat_keywords": [],
        "current_project_id": None,
        "current_task_id": None,
    }

    started = datetime.now().astimezone() - timedelta(minutes=5)
    sid = db.start_session(
        app_name="code.exe",
        window_title="main.py - VS Code",
        url_hint=None,
        category="productive",
        display_name="VS Code",
        activity_kind="work",
        activity_label="VS Code",
        started_at=started,
    )
    tracker._current_session_id = sid
    tracker._current_key = ("code.exe", "main.py - VS Code")
    tracker._current_category = "productive"
    tracker._current_label = "VS Code"
    tracker._idle = True
    tracker._idle_since = time.time() - 600
    tracker._still_working_prompting = False
    tracker._last_tick_at = time.time() - 1800  # 30 min sleep gap

    win = ActiveWindow(
        app_name="code.exe",
        window_title="main.py - VS Code",
        pid=1,
        app_path=None,
    )
    monkeypatch.setattr("deskline.tracker.get_active_window", lambda: win)
    monkeypatch.setattr("deskline.tracker.is_idle", lambda *_a, **_k: False)
    prompt = MagicMock()
    monkeypatch.setattr(tracker, "_maybe_still_working", prompt)

    before = time.time()
    tracker._tick()

    row = None
    # Session should be closed; sleep wall time must not inflate duration
    with db.connect() as conn:
        ended = conn.execute(
            "SELECT ended_at, duration_sec FROM sessions WHERE id=?", (sid,)
        ).fetchone()
    assert ended is not None
    assert ended["ended_at"] is not None
    # Sleep wall time must not inflate duration (~5 min open, not 35)
    assert float(ended["duration_sec"] or 0) < 15 * 60

    assert tracker.paused is False
    assert tracker._idle_since is None
    assert tracker._suppress_still_working_until >= before + 299
    # New session after wake
    assert tracker._current_session_id is not None
    assert tracker._current_session_id != sid


def test_still_working_timeout_keeps_tracking(tmp_path: Path, monkeypatch):
    data = tmp_path / "Deskline"
    monkeypatch.setattr("deskline.config.DATA_ROOT", data)
    monkeypatch.setattr("deskline.config.DB_PATH", data / "deskline.db")
    monkeypatch.setattr("deskline.config.SCREENSHOTS_DIR", data / "screenshots")
    monkeypatch.setattr("deskline.config.ICONS_DIR", data / "icons")
    monkeypatch.setattr("deskline.config.CONFIG_PATH", data / "config.json")
    data.mkdir(parents=True)
    (data / "screenshots").mkdir()
    (data / "icons").mkdir()

    db = Database(data / "deskline.db")
    tracker = Tracker(db)
    tracker.cfg["paused"] = False
    monkeypatch.setattr(
        "deskline.tracker.ask_still_working",
        lambda *a, **k: "timeout",
    )
    monkeypatch.setattr("deskline.tracker.notify", lambda *a, **k: None)
    tracker._ask_still_working("Тест")
    assert tracker.paused is False


def test_still_working_no_pauses(tmp_path: Path, monkeypatch):
    data = tmp_path / "Deskline"
    monkeypatch.setattr("deskline.config.DATA_ROOT", data)
    monkeypatch.setattr("deskline.config.DB_PATH", data / "deskline.db")
    monkeypatch.setattr("deskline.config.SCREENSHOTS_DIR", data / "screenshots")
    monkeypatch.setattr("deskline.config.ICONS_DIR", data / "icons")
    monkeypatch.setattr("deskline.config.CONFIG_PATH", data / "config.json")
    data.mkdir(parents=True)
    (data / "screenshots").mkdir()
    (data / "icons").mkdir()

    db = Database(data / "deskline.db")
    tracker = Tracker(db)
    tracker.cfg["paused"] = False
    monkeypatch.setattr(
        "deskline.tracker.ask_still_working",
        lambda *a, **k: "no",
    )
    monkeypatch.setattr("deskline.tracker.notify", lambda *a, **k: None)
    tracker._ask_still_working("Тест")
    assert tracker.paused is True
