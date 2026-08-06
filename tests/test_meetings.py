from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi.testclient import TestClient

from deskline.config import DEFAULT_CONFIG, ensure_data_dirs, save_config
from deskline.db import Database
from deskline.meetings import (
    build_meetings_report,
    is_meeting_app,
    is_meeting_site,
    meeting_app_label,
)


def test_meeting_allowlist_helpers():
    assert is_meeting_app("Teams.exe")
    assert is_meeting_app(r"C:\Program Files\Zoom\bin\Zoom.exe")
    assert not is_meeting_app("chrome.exe")
    assert is_meeting_site("meet.google.com")
    assert is_meeting_site("www.zoom.us")
    assert is_meeting_site("us05web.zoom.us")
    assert not is_meeting_site("telegram.org")
    assert meeting_app_label("zoom.exe") == "Zoom"


def test_build_meetings_report_filters_and_totals():
    report = build_meetings_report(
        by_app=[
            {"app_name": "zoom.exe", "name": "Zoom", "sec": 600},
            {"app_name": "chrome.exe", "name": "Chrome", "sec": 900},
        ],
        by_site=[
            {"name": "meet.google.com", "sec": 300},
            {"name": "youtube.com", "sec": 120},
        ],
        sessions=[
            {
                "started_at": "2026-07-22T10:00:00+00:00",
                "ended_at": "2026-07-22T10:10:00+00:00",
                "sec": 600,
                "app_name": "zoom.exe",
                "name": "Zoom",
            },
            {
                "started_at": "2026-07-22T11:00:00+00:00",
                "ended_at": "2026-07-22T11:05:00+00:00",
                "sec": 300,
                "app_name": "msedge.exe",
                "site": "meet.google.com",
                "name": "Google Meet",
            },
            {
                "started_at": "2026-07-22T12:00:00+00:00",
                "sec": 100,
                "app_name": "notepad.exe",
                "name": "Notepad",
            },
        ],
        total_tracked_sec=1800,
    )
    assert report["total_sec"] == 900.0
    assert report["share_pct"] == 50.0
    assert len(report["by_app"]) == 1
    assert len(report["by_site"]) == 1
    assert len(report["sessions"]) == 2
    assert "фокусе" in report["note"].casefold() or "окна" in report["note"].casefold()


def test_meetings_for_range_counts_apps_and_sites(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("deskline.config.CONFIG_PATH", tmp_path / "config.json")
    monkeypatch.setattr("deskline.config.DATA_ROOT", tmp_path)
    monkeypatch.setattr("deskline.config.DB_PATH", tmp_path / "deskline.db")
    save_config({**DEFAULT_CONFIG, "work_mode": False})

    db = Database(tmp_path / "deskline.db")
    now = datetime.now().astimezone()
    start = now - timedelta(hours=2)
    end = now

    sid_zoom = db.start_session(
        "zoom.exe",
        "Zoom Meeting",
        None,
        "productive",
        display_name="Zoom",
        activity_kind="messaging",
        activity_label="Zoom",
        started_at=start,
    )
    db.end_session(sid_zoom, ended_at=start + timedelta(minutes=20))

    sid_meet = db.start_session(
        "msedge.exe",
        "Meet - Google Meet",
        "meet.google.com",
        "productive",
        display_name="Microsoft Edge",
        activity_kind="messaging",
        activity_label="Google Meet",
        started_at=start + timedelta(minutes=30),
    )
    db.end_session(sid_meet, ended_at=start + timedelta(minutes=45))

    sid_other = db.start_session(
        "code.exe",
        "main.py - VS Code",
        None,
        "productive",
        display_name="VS Code",
        activity_kind="coding",
        activity_label="VS Code",
        started_at=start + timedelta(minutes=50),
    )
    db.end_session(sid_other, ended_at=start + timedelta(minutes=80))

    report = db.meetings_for_range(start, end)
    assert report["total_sec"] >= 34 * 60  # ~20 + ~15 min
    assert any(r["app_name"] == "zoom.exe" for r in report["by_app"])
    assert any(r["site"] == "meet.google.com" for r in report["by_site"])
    assert all(
        (r.get("app_name") == "zoom.exe") or (r.get("site") == "meet.google.com")
        for r in report["sessions"]
    )


def test_meetings_api(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("DESKLINE_LICENSE_DEV", "1")
    monkeypatch.setattr("deskline.config.DATA_ROOT", tmp_path)
    monkeypatch.setattr("deskline.config.DB_PATH", tmp_path / "deskline.db")
    monkeypatch.setattr("deskline.config.SCREENSHOTS_DIR", tmp_path / "screenshots")
    monkeypatch.setattr("deskline.config.CONFIG_PATH", tmp_path / "config.json")
    monkeypatch.setattr("deskline.config.ICONS_DIR", tmp_path / "icons")
    monkeypatch.setattr("deskline.auth.AUTH_PATH", tmp_path / "auth.json")
    monkeypatch.setattr("deskline.capture.SCREENSHOTS_DIR", tmp_path / "screenshots")
    monkeypatch.setattr("deskline.license_store.LICENSE_PATH", tmp_path / "license.json")
    (tmp_path / "screenshots").mkdir()
    (tmp_path / "icons").mkdir()

    from deskline.api import create_app
    from deskline.auth import set_password
    from deskline.tracker import Tracker

    ensure_data_dirs()
    save_config(
        {
            **DEFAULT_CONFIG,
            "first_run_at": (datetime.now(timezone.utc) - timedelta(days=30)).isoformat(),
            "onboarding_done": True,
        }
    )
    set_password("test-pass-1234")
    db = Database(tmp_path / "deskline.db")
    start = datetime.now().astimezone() - timedelta(minutes=30)
    sid = db.start_session(
        "teams.exe",
        "Standup | Microsoft Teams",
        None,
        "productive",
        display_name="Microsoft Teams",
        activity_kind="messaging",
        activity_label="Microsoft Teams",
        started_at=start,
    )
    db.end_session(sid, ended_at=start + timedelta(minutes=12))

    tracker = Tracker(db)
    tracker.cfg["paused"] = True
    client = TestClient(create_app(tracker, db))
    login = client.post(
        "/api/auth/login",
        json={"username": "owner", "password": "test-pass-1234", "remember": False},
    )
    assert login.status_code == 200
    assert client.post("/api/license/activate", json={"key": "DESKLINE-PRO-DEV"}).status_code == 200

    res = client.get("/api/meetings?period=today")
    assert res.status_code == 200
    body = res.json()
    assert body["period"] == "today"
    assert body["total_sec"] >= 11 * 60
    assert any(r["app_name"] == "teams.exe" for r in body["by_app"])
    assert body["note"]
