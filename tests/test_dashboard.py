from __future__ import annotations

from deskline.api import create_app
from deskline.auth import set_password
from deskline.db import Database
from deskline.tracker import Tracker


def test_dashboard_index_ok(tmp_path, monkeypatch):
    monkeypatch.setattr("deskline.config.DATA_ROOT", tmp_path)
    monkeypatch.setattr("deskline.config.DB_PATH", tmp_path / "deskline.db")
    monkeypatch.setattr("deskline.config.SCREENSHOTS_DIR", tmp_path / "screenshots")
    monkeypatch.setattr("deskline.config.CONFIG_PATH", tmp_path / "config.json")
    monkeypatch.setattr("deskline.auth.AUTH_PATH", tmp_path / "auth.json")
    monkeypatch.setattr("deskline.capture.SCREENSHOTS_DIR", tmp_path / "screenshots")

    set_password("test-pass")

    db = Database(tmp_path / "deskline.db")
    tracker = Tracker(db)
    tracker.cfg["paused"] = True
    app = create_app(tracker, db)

    from fastapi.testclient import TestClient

    client = TestClient(app)
    client.post("/api/auth/login", json={"password": "test-pass"})
    res = client.get("/")
    assert res.status_code == 200
    assert "Deskline" in res.text
    assert 'class="app-shell"' in res.text
    assert 'class="sidebar"' in res.text
    assert 'role="tabpanel"' in res.text
    assert 'id="toastRegion"' in res.text
    assert 'id="shotLightbox"' in res.text
    assert 'aria-modal="true"' in res.text

    settings = client.get("/api/settings")
    assert settings.status_code == 200
    body = settings.json()
    assert body["screenshot_retention_days"] == 7
    assert "screenshots_path" in body
    assert "screenshots_storage" in body
