from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock

from deskline.db import Database
from deskline.tracker import Tracker


def test_summary_includes_unassigned_project(tmp_path: Path):
    db = Database(tmp_path / "focus.db")
    start = datetime.now().astimezone() - timedelta(minutes=40)
    sid = db.start_session(
        "cursor.exe",
        "a.py",
        None,
        "productive",
        started_at=start,
        display_name="Cursor",
        activity_kind="work",
        activity_label="Разработка",
        project_id=None,
        task_id=None,
    )
    db.end_session(sid, ended_at=start + timedelta(minutes=20))
    summary = db.summary_for_day()
    assert any(p["project_id"] is None and p["sec"] >= 1100 for p in summary["by_project"])


def test_summary_filters_by_task(tmp_path: Path):
    db = Database(tmp_path / "task.db")
    start = datetime.now().astimezone() - timedelta(minutes=40)
    sid1 = db.start_session(
        "cursor.exe",
        "a.py",
        None,
        "productive",
        started_at=start,
        display_name="Cursor",
        activity_kind="work",
        activity_label="Разработка",
        project_id=1,
        task_id=10,
    )
    db.end_session(sid1, ended_at=start + timedelta(minutes=15))
    sid2 = db.start_session(
        "cursor.exe",
        "b.py",
        None,
        "productive",
        started_at=start + timedelta(minutes=15),
        display_name="Cursor",
        activity_kind="work",
        activity_label="Разработка",
        project_id=1,
        task_id=11,
    )
    db.end_session(sid2, ended_at=start + timedelta(minutes=30))
    filtered = db.summary_for_day(project_id=1, task_id=10)
    assert filtered["total_sec"] >= 800
    assert filtered["total_sec"] < 1200
    assert all(t["task_id"] == 10 for t in filtered["by_task"])


def test_apps_range_accepts_project_filter(tmp_path: Path):
    db = Database(tmp_path / "apps.db")
    start = datetime.now().astimezone() - timedelta(minutes=30)
    sid = db.start_session(
        "excel.exe",
        "Book",
        None,
        "productive",
        started_at=start,
        display_name="Excel",
        activity_kind="work",
        activity_label="Таблицы",
        project_id=5,
        task_id=1,
    )
    db.end_session(sid, ended_at=start + timedelta(minutes=20))
    end = datetime.now().astimezone()
    rows = db.apps_range(start - timedelta(minutes=1), end, project_id=5)
    assert any(r["name"] == "Excel" for r in rows)
    assert db.apps_range(start - timedelta(minutes=1), end, project_id=99) == []


def test_apply_focus_closes_current_session(tmp_path: Path, monkeypatch):
    data = tmp_path / "Deskline"
    monkeypatch.setattr("deskline.config.DATA_ROOT", data)
    monkeypatch.setattr("deskline.config.DB_PATH", data / "deskline.db")
    monkeypatch.setattr("deskline.config.SCREENSHOTS_DIR", data / "screenshots")
    monkeypatch.setattr("deskline.config.CONFIG_PATH", data / "config.json")
    monkeypatch.setattr("deskline.capture.SCREENSHOTS_DIR", data / "screenshots")

    from deskline.config import load_config, save_config

    cfg = load_config()
    cfg["current_project_id"] = 1
    cfg["current_task_id"] = 2
    save_config(cfg)

    db = Database(data / "deskline.db")
    tracker = Tracker(db)
    tracker._current_session_id = 42
    tracker._current_key = ("cursor.exe", "x")
    tracker.db.end_session = MagicMock()
    tracker.apply_focus()
    tracker.db.end_session.assert_called_once_with(42)
    assert tracker._current_session_id is None
    assert tracker._current_key is None
    assert tracker.cfg["current_project_id"] == 1
