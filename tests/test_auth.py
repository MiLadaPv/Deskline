from __future__ import annotations

from deskline.api import create_app
from deskline.auth import authenticate, register_user, set_password
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
    assert "логин" in login_page.text.lower() or "Логин" in login_page.text
    assert "пароль" in login_page.text.lower() or "Пароль" in login_page.text
    assert "Запомнить меня" in login_page.text
    assert 'id="rememberMe"' in login_page.text
    assert 'id="username"' in login_page.text

    setup = client.post(
        "/api/auth/setup",
        json={"username": "anna", "password": "secret1"},
    )
    assert setup.status_code == 200
    assert "deskline_session" in setup.cookies
    set_cookie = setup.headers.get("set-cookie", "")
    assert "Max-Age" not in set_cookie and "max-age" not in set_cookie

    ok = client.get("/api/settings")
    assert ok.status_code == 200

    taken = client.post(
        "/api/auth/setup",
        json={"username": "anna", "password": "other99"},
    )
    assert taken.status_code == 400
    assert "уже" in str(taken.json().get("detail", "")).lower()

    logout = client.post("/api/auth/logout")
    assert logout.status_code == 200
    client.cookies.clear()
    follow = client.get("/", follow_redirects=False)
    assert follow.status_code in (303, 307)
    assert "/login" in follow.headers.get("location", "")
    assert client.get("/api/settings").status_code == 401

    missing = client.post(
        "/api/auth/login",
        json={"username": "nobody", "password": "secret1"},
    )
    assert missing.status_code == 401
    assert "нет" in str(missing.json().get("detail", "")).lower()

    bad = client.post(
        "/api/auth/login",
        json={"username": "anna", "password": "wrong"},
    )
    assert bad.status_code == 401

    good = client.post(
        "/api/auth/login",
        json={"username": "anna", "password": "secret1"},
    )
    assert good.status_code == 200
    home = client.get("/")
    assert home.status_code == 200
    assert "Deskline" in home.text


def test_legacy_password_migrates_on_login(tmp_path, monkeypatch):
    _patch_paths(tmp_path, monkeypatch)
    set_password("secret2")

    user = authenticate("owner1", "secret2")
    assert user == "owner1"
    assert authenticate("owner1", "secret2") == "owner1"


def test_dashboard_requires_login_after_password(tmp_path, monkeypatch):
    _patch_paths(tmp_path, monkeypatch)
    register_user("bob", "secret2")

    db = Database(tmp_path / "deskline.db")
    tracker = Tracker(db)
    tracker.cfg["paused"] = True
    app = create_app(tracker, db)

    from fastapi.testclient import TestClient

    client = TestClient(app)
    assert client.get("/api/settings").status_code == 401
    assert client.get("/", follow_redirects=False).status_code in (303, 307)
