from __future__ import annotations

import json

from deskline.api import create_app
from deskline.auth import is_google_linked, link_google_account, set_password, setup_with_google
from deskline.db import Database
from deskline.google_oauth import GoogleOAuthConfig, build_authorize_url, make_pkce_pair
from deskline.tracker import Tracker


def _patch_paths(tmp_path, monkeypatch):
    monkeypatch.setattr("deskline.config.DATA_ROOT", tmp_path)
    monkeypatch.setattr("deskline.config.DB_PATH", tmp_path / "deskline.db")
    monkeypatch.setattr("deskline.config.SCREENSHOTS_DIR", tmp_path / "screenshots")
    monkeypatch.setattr("deskline.config.CONFIG_PATH", tmp_path / "config.json")
    monkeypatch.setattr("deskline.auth.AUTH_PATH", tmp_path / "auth.json")
    monkeypatch.setattr("deskline.capture.SCREENSHOTS_DIR", tmp_path / "screenshots")


def test_build_authorize_url_includes_pkce():
    cfg = GoogleOAuthConfig(client_id="cid.apps.googleusercontent.com", client_secret="sec")
    _, challenge = make_pkce_pair()
    url = build_authorize_url(cfg, state="abc", code_challenge=challenge)
    assert "client_id=cid.apps.googleusercontent.com" in url
    assert "code_challenge=" in url
    assert "code_challenge_method=S256" in url
    assert "redirect_uri=" in url
    assert "localhost" in url


def test_redirect_uri_uses_localhost():
    from deskline.google_oauth import redirect_uri

    assert redirect_uri().startswith("http://localhost:")
    assert redirect_uri().endswith("/api/auth/google/callback")


def test_setup_with_google_and_status(tmp_path, monkeypatch):
    _patch_paths(tmp_path, monkeypatch)
    (tmp_path / "google-oauth.json").write_text(
        json.dumps(
            {
                "installed": {
                    "client_id": "test-client.apps.googleusercontent.com",
                    "client_secret": "test-secret",
                }
            }
        ),
        encoding="utf-8",
    )
    recovery = setup_with_google("google-sub-1", "user@example.com")
    assert recovery
    assert is_google_linked()

    db = Database(tmp_path / "deskline.db")
    tracker = Tracker(db)
    tracker.cfg["paused"] = True
    app = create_app(tracker, db)
    from fastapi.testclient import TestClient

    client = TestClient(app)
    st = client.get("/api/auth/status").json()
    assert st["google_configured"] is True
    assert st["google_linked"] is True
    assert st["auth_configured"] is True
    assert st["password_set"] is False

    start = client.get("/api/auth/google/start", follow_redirects=False)
    assert start.status_code in (302, 303)
    assert "accounts.google.com" in start.headers["location"]


def test_google_callback_login_linked(tmp_path, monkeypatch):
    _patch_paths(tmp_path, monkeypatch)
    (tmp_path / "google-oauth.json").write_text(
        json.dumps(
            {
                "installed": {
                    "client_id": "test-client.apps.googleusercontent.com",
                    "client_secret": "test-secret",
                }
            }
        ),
        encoding="utf-8",
    )
    set_password("pass1234", issue_recovery=True)
    link_google_account("sub-xyz", "a@example.com")

    db = Database(tmp_path / "deskline.db")
    tracker = Tracker(db)
    tracker.cfg["paused"] = True
    app = create_app(tracker, db)
    from fastapi.testclient import TestClient

    client = TestClient(app)

    monkeypatch.setattr(
        "deskline.api.exchange_code",
        lambda cfg, code, code_verifier: {"access_token": "tok", "id_token": "x.y.z"},
    )
    monkeypatch.setattr(
        "deskline.api.resolve_google_identity",
        lambda tokens: ("sub-xyz", "a@example.com"),
    )

    start = client.get("/api/auth/google/start", follow_redirects=False)
    assert start.status_code in (302, 303)
    loc = start.headers["location"]
    from urllib.parse import parse_qs, urlparse

    state = parse_qs(urlparse(loc).query)["state"][0]
    cb = client.get(
        f"/api/auth/google/callback?code=fake&state={state}",
        follow_redirects=False,
    )
    assert cb.status_code in (302, 303)
    assert cb.headers["location"] in ("/", "http://testserver/")
    assert client.cookies.get("deskline_session")


def test_google_start_allowed_when_password_set_without_link(tmp_path, monkeypatch):
    _patch_paths(tmp_path, monkeypatch)
    (tmp_path / "google-oauth.json").write_text(
        json.dumps(
            {
                "installed": {
                    "client_id": "test-client.apps.googleusercontent.com",
                    "client_secret": "test-secret",
                }
            }
        ),
        encoding="utf-8",
    )
    set_password("pass1234", issue_recovery=True)
    assert not is_google_linked()

    db = Database(tmp_path / "deskline.db")
    tracker = Tracker(db)
    tracker.cfg["paused"] = True
    app = create_app(tracker, db)
    from fastapi.testclient import TestClient

    client = TestClient(app)
    start = client.get("/api/auth/google/start", follow_redirects=False)
    assert start.status_code in (302, 303)
    assert "accounts.google.com" in start.headers["location"]


def test_google_callback_registers_new_user_alongside_password(tmp_path, monkeypatch):
    _patch_paths(tmp_path, monkeypatch)
    (tmp_path / "google-oauth.json").write_text(
        json.dumps(
            {
                "installed": {
                    "client_id": "test-client.apps.googleusercontent.com",
                    "client_secret": "test-secret",
                }
            }
        ),
        encoding="utf-8",
    )
    set_password("pass1234", issue_recovery=True)

    db = Database(tmp_path / "deskline.db")
    tracker = Tracker(db)
    tracker.cfg["paused"] = True
    app = create_app(tracker, db)
    from fastapi.testclient import TestClient

    client = TestClient(app)

    monkeypatch.setattr(
        "deskline.api.exchange_code",
        lambda cfg, code, code_verifier: {"access_token": "tok", "id_token": "x.y.z"},
    )
    monkeypatch.setattr(
        "deskline.api.resolve_google_identity",
        lambda tokens: ("sub-new-google", "anna.smith@example.com"),
    )

    start = client.get("/api/auth/google/start", follow_redirects=False)
    assert start.status_code in (302, 303)
    loc = start.headers["location"]
    from urllib.parse import parse_qs, urlparse

    state = parse_qs(urlparse(loc).query)["state"][0]
    cb = client.get(
        f"/api/auth/google/callback?code=fake&state={state}",
        follow_redirects=False,
    )
    assert cb.status_code in (302, 303)
    # New Google user gets a recovery code reveal on first signup.
    assert "google_recovery=" in cb.headers["location"] or cb.headers["location"] in (
        "/",
        "http://testserver/",
    )
    assert client.cookies.get("deskline_session")
    assert is_google_linked()
    from deskline.auth import username_for_google_sub

    assert username_for_google_sub("sub-new-google") == "anna.smith"


def test_login_page_has_google_button(tmp_path, monkeypatch):
    _patch_paths(tmp_path, monkeypatch)
    from deskline.config import WEB_ROOT

    text = (WEB_ROOT / "templates" / "login.html").read_text(encoding="utf-8")
    assert "googleLoginBtn" in text
    assert "googleLoginLabel" in text
    assert "google-icon" in text
    assert "/api/auth/google/start" in text
    assert "Привязать Google" not in text
    assert "Сначала войдите паролем" not in text
