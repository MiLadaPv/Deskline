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


def _deskline_tmp(tmp_path: Path, monkeypatch) -> Path:
    data = tmp_path / "Deskline"
    monkeypatch.setattr("deskline.config.DATA_ROOT", data)
    monkeypatch.setattr("deskline.config.DB_PATH", data / "deskline.db")
    monkeypatch.setattr("deskline.config.SCREENSHOTS_DIR", data / "screenshots")
    monkeypatch.setattr("deskline.config.ICONS_DIR", data / "icons")
    monkeypatch.setattr("deskline.config.CONFIG_PATH", data / "config.json")
    monkeypatch.setattr("deskline.heartbeat.DATA_ROOT", data)
    data.mkdir(parents=True)
    (data / "screenshots").mkdir()
    (data / "icons").mkdir()
    return data


def test_hard_kill_orphan_closed_at_heartbeat(tmp_path: Path, monkeypatch):
    """Battery death: open session + stale heartbeat must not resume into 'now'."""
    from deskline.heartbeat import save_heartbeat

    data = _deskline_tmp(tmp_path, monkeypatch)
    db = Database(data / "deskline.db")

    boot = time.time() - 600  # rebooted 10 min ago
    monkeypatch.setattr("deskline.tracker.system_boot_time", lambda: boot)

    started = datetime.now().astimezone() - timedelta(hours=14)
    sid = db.start_session(
        app_name="rg-soft.exe",
        window_title="RG-Soft",
        url_hint=None,
        category="productive",
        display_name="RG-Soft",
        activity_kind="work",
        activity_label="RG-Soft",
        started_at=started,
    )
    # Last tick before power loss — hours before this boot
    hb_ts = boot - 3600
    save_heartbeat(sid, hb_ts)

    tracker = Tracker(db)
    assert tracker._current_session_id is None

    with db.connect() as conn:
        row = conn.execute(
            "SELECT ended_at, duration_sec FROM sessions WHERE id=?", (sid,)
        ).fetchone()
    assert row["ended_at"] is not None
    # Closed at heartbeat, not stretched to now (~14h)
    assert float(row["duration_sec"] or 0) < 14 * 3600 - 100
    ended = datetime.fromisoformat(row["ended_at"])
    assert abs(ended.timestamp() - hb_ts) < 2.0


def test_never_resume_open_session_on_init(tmp_path: Path, monkeypatch):
    """Even a fresh heartbeat must not resume across process restart."""
    from deskline.heartbeat import save_heartbeat

    data = _deskline_tmp(tmp_path, monkeypatch)
    db = Database(data / "deskline.db")
    monkeypatch.setattr("deskline.tracker.system_boot_time", lambda: time.time() - 86400)

    started = datetime.now().astimezone() - timedelta(minutes=30)
    sid = db.start_session(
        app_name="code.exe",
        window_title="main.py",
        url_hint=None,
        category="productive",
        display_name="VS Code",
        activity_kind="work",
        activity_label="VS Code",
        started_at=started,
    )
    hb_ts = time.time() - 1.0
    save_heartbeat(sid, hb_ts)

    tracker = Tracker(db)
    assert tracker._current_session_id is None
    with db.connect() as conn:
        row = conn.execute(
            "SELECT ended_at FROM sessions WHERE id=?", (sid,)
        ).fetchone()
    assert row["ended_at"] is not None


def test_repair_phantom_overnight_zero_idle(tmp_path: Path, monkeypatch):
    data = _deskline_tmp(tmp_path, monkeypatch)
    db = Database(data / "deskline.db")

    started = datetime.now().astimezone().replace(
        hour=21, minute=49, second=0, microsecond=0
    ) - timedelta(days=1)
    ended = started + timedelta(hours=15, minutes=20)  # crosses midnight, ~13h after
    sid = db.start_session(
        app_name="rg-soft.exe",
        window_title="RG-Soft",
        url_hint=None,
        category="productive",
        display_name="RG-Soft",
        activity_kind="work",
        activity_label="RG-Soft",
        started_at=started,
    )
    db.end_session(sid, ended_at=ended)
    with db.connect() as conn:
        conn.execute("UPDATE sessions SET idle_sec=0 WHERE id=?", (sid,))

    n = db.repair_phantom_overnight_sessions()
    assert n == 1
    with db.connect() as conn:
        row = conn.execute(
            "SELECT started_at, ended_at, duration_sec FROM sessions WHERE id=?", (sid,)
        ).fetchone()
    ended_fixed = datetime.fromisoformat(row["ended_at"])
    assert ended_fixed.hour == 0 and ended_fixed.minute == 0
    # Pre-midnight evening only (~2h11m)
    assert 2 * 3600 < float(row["duration_sec"]) < 3 * 3600


def test_repair_session_spanning_boot_clamps_start(tmp_path: Path, monkeypatch):
    """Already-closed inflated session (old resume bug) is clipped to boot."""
    data = _deskline_tmp(tmp_path, monkeypatch)
    db = Database(data / "deskline.db")

    boot = time.time() - 1800  # booted 30 min ago
    started = datetime.fromtimestamp(boot - 12 * 3600).astimezone()
    ended = datetime.fromtimestamp(boot + 900).astimezone()  # 15 min after boot
    sid = db.start_session(
        app_name="rg-soft.exe",
        window_title="RG-Soft",
        url_hint=None,
        category="productive",
        display_name="RG-Soft",
        activity_kind="work",
        activity_label="RG-Soft",
        started_at=started,
    )
    db.end_session(sid, ended_at=ended)
    with db.connect() as conn:
        before = conn.execute(
            "SELECT duration_sec FROM sessions WHERE id=?", (sid,)
        ).fetchone()
    assert float(before["duration_sec"]) > 10 * 3600

    n = db.repair_sessions_spanning_boot(boot)
    assert n == 1
    with db.connect() as conn:
        row = conn.execute(
            "SELECT started_at, duration_sec FROM sessions WHERE id=?", (sid,)
        ).fetchone()
    assert abs(float(row["duration_sec"]) - 900) < 2.0
    assert abs(datetime.fromisoformat(row["started_at"]).timestamp() - boot) < 2.0


def test_tracker_init_repairs_spanning_boot_session(tmp_path: Path, monkeypatch):
    data = _deskline_tmp(tmp_path, monkeypatch)
    db = Database(data / "deskline.db")
    boot = time.time() - 900
    monkeypatch.setattr("deskline.tracker.system_boot_time", lambda: boot)

    started = datetime.fromtimestamp(boot - 10 * 3600).astimezone()
    ended = datetime.fromtimestamp(boot + 600).astimezone()
    sid = db.start_session(
        app_name="code.exe",
        window_title="app",
        url_hint=None,
        category="productive",
        display_name="VS Code",
        activity_kind="work",
        activity_label="VS Code",
        started_at=started,
    )
    db.end_session(sid, ended_at=ended)

    Tracker(db)
    with db.connect() as conn:
        row = conn.execute(
            "SELECT duration_sec FROM sessions WHERE id=?", (sid,)
        ).fetchone()
    assert float(row["duration_sec"]) < 700


def test_tracker_init_repairs_phantom_overnight(tmp_path: Path, monkeypatch):
    data = _deskline_tmp(tmp_path, monkeypatch)
    db = Database(data / "deskline.db")
    monkeypatch.setattr("deskline.tracker.system_boot_time", lambda: time.time() - 86400 * 4)

    started = datetime.now().astimezone().replace(
        hour=21, minute=50, second=0, microsecond=0
    ) - timedelta(days=1)
    ended = started + timedelta(hours=15)
    sid = db.start_session(
        app_name="app.exe",
        window_title="x",
        url_hint=None,
        category="productive",
        display_name="App",
        activity_kind="work",
        activity_label="App",
        started_at=started,
    )
    db.end_session(sid, ended_at=ended)
    with db.connect() as conn:
        conn.execute("UPDATE sessions SET idle_sec=0 WHERE id=?", (sid,))

    Tracker(db)
    day = datetime.now().astimezone().date()
    s = db.summary_for_day(day)
    # Overnight phantom removed — today should not show ~13h from that row
    assert float(s.get("total_sec") or 0) < 3600
