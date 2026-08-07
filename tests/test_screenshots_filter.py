from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi.testclient import TestClient

from deskline.config import DEFAULT_CONFIG, ensure_data_dirs, load_config, save_config
from deskline.db import Database


def test_screenshots_include_session_app_fields(tmp_path: Path, monkeypatch):
    shots = tmp_path / "shots"
    shots.mkdir()
    monkeypatch.setattr("deskline.config.SCREENSHOTS_DIR", shots)
    monkeypatch.setattr("deskline.config.CONFIG_PATH", tmp_path / "config.json")
    monkeypatch.setattr("deskline.config.DATA_ROOT", tmp_path)
    monkeypatch.setattr("deskline.config.DB_PATH", tmp_path / "deskline.db")
    monkeypatch.setattr("deskline.config.ICONS_DIR", tmp_path / "icons")
    (tmp_path / "icons").mkdir(exist_ok=True)

    db = Database(tmp_path / "deskline.db")
    start = datetime.now().astimezone() - timedelta(minutes=5)
    sid = db.start_session(
        app_name="msedge.exe",
        window_title="Cats - YouTube",
        url_hint="youtube.com",
        category="distracting",
        display_name="Microsoft Edge",
        activity_kind="video",
        activity_label="YouTube",
        started_at=start,
    )
    path = shots / "edge.jpg"
    path.write_bytes(b"jpg")
    db.add_screenshot(str(path), reason="interval", session_id=sid)

    rows = db.screenshots_for_date()
    assert rows
    edge = rows[0]
    assert edge["app_name"] == "msedge.exe"
    assert edge["display_name"] == "Microsoft Edge"
    assert edge["activity_label"] == "YouTube"
    assert "YouTube" in (edge["window_title"] or "")


def test_screenshots_api_app_filter(tmp_path: Path, monkeypatch):
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
            "screenshots_enabled": True,
        }
    )
    set_password("test-pass-1234")
    db = Database(tmp_path / "deskline.db")
    start = datetime.now().astimezone() - timedelta(minutes=3)
    sid = db.start_session(
        "msedge.exe",
        "News",
        None,
        "neutral",
        display_name="Microsoft Edge",
        activity_kind="other",
        activity_label="Edge",
        started_at=start,
    )
    p = tmp_path / "screenshots" / "e.jpg"
    p.write_bytes(b"jpg")
    db.add_screenshot(str(p), reason="interval", session_id=sid)

    sid2 = db.start_session(
        "Code.exe",
        "main.py",
        None,
        "productive",
        display_name="Cursor",
        activity_kind="work",
        activity_label="Код",
        started_at=start + timedelta(minutes=1),
    )
    p2 = tmp_path / "screenshots" / "c.jpg"
    p2.write_bytes(b"jpg")
    db.add_screenshot(str(p2), reason="app_switch", session_id=sid2)

    yesterday = datetime.now().astimezone() - timedelta(days=1)
    p3 = tmp_path / "screenshots" / "y.jpg"
    p3.write_bytes(b"jpg")
    db.add_screenshot(str(p3), reason="interval", session_id=sid, taken_at=yesterday)

    tracker = Tracker(db)
    tracker.cfg["paused"] = True
    client = TestClient(create_app(tracker, db))
    client.post(
        "/api/auth/login",
        json={"username": "owner", "password": "test-pass-1234", "remember": False},
    )
    assert client.post("/api/license/activate", json={"key": "DESKLINE-PRO-DEV"}).status_code == 200

    all_rows = client.get("/api/screenshots").json()
    assert len(all_rows) >= 2
    assert any(x.get("display_name") == "Microsoft Edge" for x in all_rows)

    filtered = client.get("/api/screenshots", params={"app": "msedge"}).json()
    assert filtered
    assert all(str(x.get("app_name") or "").lower().startswith("msedge") for x in filtered)
    assert all(x.get("display_name") == "Microsoft Edge" for x in filtered)

    days_payload = client.get("/api/screenshots/days").json()
    days = days_payload["days"]
    assert isinstance(days, list)
    today = datetime.now().astimezone().date().isoformat()
    yday = yesterday.astimezone().date().isoformat()
    assert today in days
    assert yday in days
    assert days.index(today) < days.index(yday) or today == yday


def test_screenshot_days_db(tmp_path: Path, monkeypatch):
    shots = tmp_path / "shots"
    shots.mkdir()
    monkeypatch.setattr("deskline.config.SCREENSHOTS_DIR", shots)
    monkeypatch.setattr("deskline.config.CONFIG_PATH", tmp_path / "config.json")
    monkeypatch.setattr("deskline.config.DATA_ROOT", tmp_path)
    monkeypatch.setattr("deskline.config.DB_PATH", tmp_path / "deskline.db")
    monkeypatch.setattr("deskline.config.ICONS_DIR", tmp_path / "icons")
    (tmp_path / "icons").mkdir(exist_ok=True)

    db = Database(tmp_path / "deskline.db")
    assert db.screenshot_days() == []

    now = datetime.now().astimezone()
    older = now - timedelta(days=2)
    p1 = shots / "a.jpg"
    p1.write_bytes(b"jpg")
    db.add_screenshot(str(p1), reason="interval", session_id=None, taken_at=older)
    p2 = shots / "b.jpg"
    p2.write_bytes(b"jpg")
    db.add_screenshot(str(p2), reason="interval", session_id=None, taken_at=now)

    days = db.screenshot_days()
    assert days[0] == now.date().isoformat()
    assert older.date().isoformat() in days
