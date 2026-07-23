from __future__ import annotations

from deskline.api import create_app
from deskline.db import Database
from deskline.tracker import Tracker


def _patch_paths(tmp_path, monkeypatch):
    monkeypatch.setattr("deskline.config.DATA_ROOT", tmp_path)
    monkeypatch.setattr("deskline.config.DB_PATH", tmp_path / "deskline.db")
    monkeypatch.setattr("deskline.config.SCREENSHOTS_DIR", tmp_path / "screenshots")
    monkeypatch.setattr("deskline.config.CONFIG_PATH", tmp_path / "config.json")
    monkeypatch.setattr("deskline.auth.AUTH_PATH", tmp_path / "auth.json")
    monkeypatch.setattr("deskline.capture.SCREENSHOTS_DIR", tmp_path / "screenshots")


def test_extension_status_and_event_public(tmp_path, monkeypatch):
    _patch_paths(tmp_path, monkeypatch)

    db = Database(tmp_path / "deskline.db")
    tracker = Tracker(db)
    tracker.cfg["paused"] = True
    app = create_app(tracker, db)

    from fastapi.testclient import TestClient

    client = TestClient(app)

    status = client.get("/api/extension/status")
    assert status.status_code == 200
    body = status.json()
    assert body["ok"] is True
    assert body["desktop"] is True

    # Too short → ignored
    short = client.post(
        "/api/extension/event",
        json={
            "url": "https://example.com/page",
            "title": "Example",
            "host": "example.com",
            "duration_sec": 0.5,
        },
    )
    assert short.status_code == 200
    assert short.json().get("ignored") is True

    ok = client.post(
        "/api/extension/event",
        json={
            "url": "https://example.com/page",
            "title": "Example",
            "host": "example.com",
            "started_at": "2026-07-22T10:00:00+00:00",
            "ended_at": "2026-07-22T10:05:00+00:00",
            "duration_sec": 300,
        },
    )
    assert ok.status_code == 200
    data = ok.json()
    assert data["ok"] is True
    assert "session_id" in data
