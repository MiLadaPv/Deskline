from __future__ import annotations

from deskline.api import create_app
from deskline.auth import set_password
from deskline.db import Database
from deskline.tracker import Tracker


def _patch_paths(tmp_path, monkeypatch):
    monkeypatch.setattr("deskline.config.DATA_ROOT", tmp_path)
    monkeypatch.setattr("deskline.config.DB_PATH", tmp_path / "deskline.db")
    monkeypatch.setattr("deskline.config.SCREENSHOTS_DIR", tmp_path / "screenshots")
    monkeypatch.setattr("deskline.config.CONFIG_PATH", tmp_path / "config.json")
    monkeypatch.setattr("deskline.auth.AUTH_PATH", tmp_path / "auth.json")
    monkeypatch.setattr("deskline.capture.SCREENSHOTS_DIR", tmp_path / "screenshots")


def test_auth_setup_login_and_gate(tmp_path, monkeypatch):
    _patch_paths(tmp_path, monkeypatch)

    db = Database(tmp_path / "deskline.db")
    tracker = Tracker(db)
    tracker.cfg["paused"] = True
    app = create_app(tracker, db)

    from fastapi.testclient import TestClient

    client = TestClient(app)

    denied = client.get("/api/settings")
    assert denied.status_code == 401

    login_page = client.get("/login")
    assert login_page.status_code == 200
    assert "пароль" in login_page.text.lower() or "Пароль" in login_page.text

    setup = client.post("/api/auth/setup", json={"password": "secret1"})
    assert setup.status_code == 200
    assert "deskline_session" in setup.cookies

    ok = client.get("/api/settings")
    assert ok.status_code == 200

    client.post("/api/auth/logout")
    denied2 = client.get("/")
    assert denied2.status_code in (303, 307, 401, 200)
    # After logout, unauthenticated HTML should redirect to login
    follow = client.get("/", follow_redirects=False)
    assert follow.status_code in (303, 307)
    assert "/login" in follow.headers.get("location", "")

    bad = client.post("/api/auth/login", json={"password": "wrong"})
    assert bad.status_code == 401

    good = client.post("/api/auth/login", json={"password": "secret1"})
    assert good.status_code == 200
    home = client.get("/")
    assert home.status_code == 200
    assert "Deskline" in home.text


def test_dashboard_requires_login_after_password(tmp_path, monkeypatch):
    _patch_paths(tmp_path, monkeypatch)
    set_password("secret2")

    db = Database(tmp_path / "deskline.db")
    tracker = Tracker(db)
    tracker.cfg["paused"] = True
    app = create_app(tracker, db)

    from fastapi.testclient import TestClient

    client = TestClient(app)
    res = client.get("/", follow_redirects=False)
    assert res.status_code in (303, 307)

    client.post("/api/auth/login", json={"password": "secret2"})
    settings = client.get("/api/settings")
    assert settings.status_code == 200
    assert settings.json()["screenshot_retention_days"] == 7
