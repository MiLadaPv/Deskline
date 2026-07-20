from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from deskline.db import Database
from deskline.idle import is_idle


def test_is_idle_threshold(monkeypatch):
    with patch("deskline.idle.seconds_since_last_input", return_value=50):
        assert is_idle(180) is False
    with patch("deskline.idle.seconds_since_last_input", return_value=200):
        assert is_idle(180) is True


def test_meeting_apps_use_longer_idle(monkeypatch):
    with patch("deskline.idle.seconds_since_last_input", return_value=300):
        assert is_idle(180, "notepad.exe") is True
        assert is_idle(180, "teams.exe") is False
    with patch("deskline.idle.seconds_since_last_input", return_value=1000):
        assert is_idle(180, "zoom.exe") is True


def test_summary_separates_focus_and_activity(tmp_path: Path):
    db = Database(tmp_path / "idle.db")
    start = datetime.now().astimezone() - timedelta(minutes=20)

    sid = db.start_session(
        "cursor.exe",
        "main.py",
        None,
        "productive",
        started_at=start,
        display_name="Cursor",
        activity_kind="work",
        activity_label="Разработка",
    )
    db.add_idle_seconds(sid, 600)  # 10 min idle of 20
    db.end_session(sid, ended_at=start + timedelta(minutes=20))

    sid2 = db.start_session(
        "spotify.exe",
        "Music",
        None,
        "distracting",
        started_at=start + timedelta(minutes=20),
        display_name="Spotify",
        activity_kind="video",
        activity_label="Музыка",
    )
    db.end_session(sid2, ended_at=start + timedelta(minutes=30))

    summary = db.summary_for_day()
    assert summary["total_sec"] >= 1700
    assert summary["focus_sec"] >= 1100
    assert summary["idle_sec"] >= 500
    assert summary["active_sec"] == summary["total_sec"] - summary["idle_sec"]
    assert 0 <= summary["activity_pct"] <= 100
    # Idle does not remove productive time from focus (TD rule)
    assert summary["focus_pct"] > 0
