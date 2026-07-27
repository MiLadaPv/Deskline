"""Freemium entitlements and license activation."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from deskline.entitlements import (
    FREE_HISTORY_DAYS,
    FREE_MAX_PROJECTS,
    resolve_entitlements,
    trial_active,
)
from deskline.license_client import activate_license, deactivate_local
from deskline.license_store import clear_license, load_license, save_license


@pytest.fixture()
def iso_now():
    return datetime(2026, 7, 23, 12, 0, tzinfo=timezone.utc)


def test_trial_then_free(iso_now):
    first = (iso_now - timedelta(days=2)).isoformat()
    ent = resolve_entitlements({"first_run_at": first}, None, now=iso_now)
    assert ent.tier == "trial"
    assert ent.screenshots is True
    assert ent.export is True

    first_old = (iso_now - timedelta(days=20)).isoformat()
    ent2 = resolve_entitlements({"first_run_at": first_old}, None, now=iso_now)
    assert ent2.tier == "free"
    assert ent2.history_days == FREE_HISTORY_DAYS
    assert ent2.max_projects == FREE_MAX_PROJECTS
    assert ent2.screenshots is False


def test_pro_license_unlocks(iso_now, monkeypatch, tmp_path: Path):
    monkeypatch.setenv("DESKLINE_LICENSE_DEV", "1")
    monkeypatch.setattr("deskline.config.DATA_ROOT", tmp_path)
    monkeypatch.setattr("deskline.license_store.LICENSE_PATH", tmp_path / "license.json")
    tmp_path.mkdir(parents=True, exist_ok=True)

    clear_license()
    activate_license("DESKLINE-PRO-DEV")
    lic = load_license()
    assert lic and lic["tier"] == "pro"
    ent = resolve_entitlements(
        {"first_run_at": (iso_now - timedelta(days=40)).isoformat()}, lic, now=iso_now
    )
    assert ent.is_pro
    assert ent.company_hub is False
    deactivate_local()
    assert load_license() is None


def test_offline_grace_expires(iso_now):
    lic = {
        "key": "X",
        "tier": "pro",
        "status": "active",
        "expires_at": None,
        "last_validated_at": (iso_now - timedelta(days=20)).isoformat(),
    }
    ent = resolve_entitlements({"first_run_at": ""}, lic, now=iso_now)
    assert ent.tier == "free"


def test_api_project_limit_and_license(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("DESKLINE_LICENSE_DEV", "1")
    monkeypatch.setattr("deskline.config.DATA_ROOT", tmp_path)
    monkeypatch.setattr("deskline.config.DB_PATH", tmp_path / "deskline.db")
    monkeypatch.setattr("deskline.config.SCREENSHOTS_DIR", tmp_path / "screenshots")
    monkeypatch.setattr("deskline.config.CONFIG_PATH", tmp_path / "config.json")
    monkeypatch.setattr("deskline.config.ICONS_DIR", tmp_path / "icons")
    monkeypatch.setattr("deskline.auth.AUTH_PATH", tmp_path / "auth.json")
    monkeypatch.setattr("deskline.capture.SCREENSHOTS_DIR", tmp_path / "screenshots")
    monkeypatch.setattr("deskline.license_store.LICENSE_PATH", tmp_path / "license.json")

    from deskline.api import create_app
    from deskline.auth import set_password
    from deskline.config import DEFAULT_CONFIG, ensure_data_dirs, save_config
    from deskline.db import Database
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
    tracker = Tracker(db)
    tracker.cfg["paused"] = True
    client = TestClient(create_app(tracker, db))
    client.post("/api/auth/login", json={"username": "owner", "password": "test-pass-1234", "remember": False})

    for i in range(FREE_MAX_PROJECTS):
        r = client.post("/api/projects", json={"name": f"P{i}", "color": "#123456"})
        assert r.status_code == 200, r.text
    r = client.post("/api/projects", json={"name": "Overflow", "color": "#123456"})
    assert r.status_code == 402

    r = client.post("/api/license/activate", json={"key": "DESKLINE-PRO-DEV"})
    assert r.status_code == 200
    assert r.json()["entitlements"]["is_pro"] is True
    r = client.post("/api/projects", json={"name": "ProProject", "color": "#123456"})
    assert r.status_code == 200

    r = client.get("/api/export/json")
    assert r.status_code == 200
    assert "deskline-export.json" in r.headers.get("content-disposition", "")

    r = client.put("/api/settings", json={"company_mode": True})
    assert r.status_code == 402

    r = client.post("/api/license/activate", json={"key": "DESKLINE-TEAM-DEV"})
    assert r.status_code == 200
    assert r.json()["entitlements"]["company_hub"] is True
    r = client.put("/api/settings", json={"company_mode": True, "company_display_name": "Demo Co"})
    assert r.status_code == 200
    r = client.get("/api/company")
    assert r.status_code == 200
    assert r.json().get("company_mode") is True


def test_team_license_unlocks_hub(iso_now, monkeypatch, tmp_path: Path):
    monkeypatch.setenv("DESKLINE_LICENSE_DEV", "1")
    monkeypatch.setattr("deskline.config.DATA_ROOT", tmp_path)
    monkeypatch.setattr("deskline.license_store.LICENSE_PATH", tmp_path / "license.json")
    tmp_path.mkdir(parents=True, exist_ok=True)

    clear_license()
    activate_license("DESKLINE-TEAM-DEV")
    lic = load_license()
    assert lic and lic["tier"] == "team"
    ent = resolve_entitlements(
        {"first_run_at": (iso_now - timedelta(days=40)).isoformat()}, lic, now=iso_now
    )
    assert ent.is_team
    assert ent.is_pro
    assert ent.company_hub is True
    from deskline.entitlements import checkout_urls

    assert "team" in checkout_urls()
    deactivate_local()


def test_welcome_and_compare_public(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("deskline.config.DATA_ROOT", tmp_path)
    monkeypatch.setattr("deskline.config.DB_PATH", tmp_path / "deskline.db")
    monkeypatch.setattr("deskline.config.SCREENSHOTS_DIR", tmp_path / "screenshots")
    monkeypatch.setattr("deskline.config.CONFIG_PATH", tmp_path / "config.json")
    monkeypatch.setattr("deskline.config.ICONS_DIR", tmp_path / "icons")
    monkeypatch.setattr("deskline.auth.AUTH_PATH", tmp_path / "auth.json")
    from deskline.api import create_app
    from deskline.db import Database
    from deskline.tracker import Tracker

    db = Database(tmp_path / "deskline.db")
    client = TestClient(create_app(Tracker(db), db))
    r = client.get("/welcome")
    assert r.status_code == 200
    assert "Free" in r.text and "Pro" in r.text and "Team" in r.text
    assert 'href="/download"' in r.text
    assert "og:title" in r.text
    r2 = client.get("/docs/compare")
    assert r2.status_code == 200
    assert "Time Doctor" in r2.text
    r3 = client.get("/download")
    assert r3.status_code == 200
    assert "Скачать Deskline для Windows" in r3.text
    assert "silent_install.bat" in r3.text
    assert 'data-os="windows"' in r3.text
    bat = client.get("/static/install/silent_install.bat")
    assert bat.status_code == 200
    assert b"VERYSILENT" in bat.content or b"silent_install.ps1" in bat.content


def test_funnel_events(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("deskline.config.DATA_ROOT", tmp_path)
    monkeypatch.setattr("deskline.funnel.DATA_ROOT", tmp_path)
    tmp_path.mkdir(parents=True, exist_ok=True)
    from deskline.funnel import read_funnel_tail, record_funnel_event

    assert record_funnel_event("welcome_view")
    assert not record_funnel_event("not_a_real_event")
    rows = read_funnel_tail(10)
    assert rows and rows[-1]["event"] == "welcome_view"


def test_trial_active_helper(iso_now):
    ok, ends = trial_active({"first_run_at": iso_now.isoformat()}, now=iso_now)
    assert ok and ends is not None
