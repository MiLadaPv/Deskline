from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

from fastapi.testclient import TestClient

from deskline.api import create_app
from deskline.auth import set_password
from deskline.company_tokens import hash_ingest_token
from deskline.db import Database
from deskline.tracker import Tracker


def _patch_paths(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("deskline.config.DATA_ROOT", tmp_path)
    monkeypatch.setattr("deskline.config.DB_PATH", tmp_path / "deskline.db")
    monkeypatch.setattr("deskline.config.SCREENSHOTS_DIR", tmp_path / "screenshots")
    monkeypatch.setattr("deskline.config.CONFIG_PATH", tmp_path / "config.json")
    monkeypatch.setattr("deskline.config.ICONS_DIR", tmp_path / "icons")
    monkeypatch.setattr("deskline.auth.AUTH_PATH", tmp_path / "auth.json")
    monkeypatch.setattr("deskline.capture.SCREENSHOTS_DIR", tmp_path / "screenshots")


def _auth_client(tmp_path: Path, monkeypatch) -> tuple[TestClient, Database]:
    _patch_paths(tmp_path, monkeypatch)
    set_password("test-pass-1234")
    db = Database(tmp_path / "deskline.db")
    tracker = Tracker(db)
    tracker.cfg["paused"] = True
    app = create_app(tracker, db)
    client = TestClient(app)
    client.post("/api/auth/login", json={"password": "test-pass-1234", "remember": False})
    return client, db


def test_default_employee_and_backfill(tmp_path: Path, monkeypatch):
    _patch_paths(tmp_path, monkeypatch)
    db = Database(tmp_path / "deskline.db")
    eid = db.ensure_default_employee()
    assert eid >= 1
    emps = db.list_employees()
    assert len(emps) == 1
    assert emps[0]["role"] == "admin"
    sid = db.start_session(
        "code.exe",
        "main.py",
        None,
        "productive",
        employee_id=None,
    )
    db.end_session(sid)
    db.ensure_default_employee()
    with db.connect() as conn:
        row = conn.execute("SELECT employee_id FROM sessions WHERE id=?", (sid,)).fetchone()
    assert int(row["employee_id"]) == eid


def test_team_summary_and_ingest(tmp_path: Path, monkeypatch):
    client, db = _auth_client(tmp_path, monkeypatch)
    created = client.post(
        "/api/company/employees",
        json={"display_name": "Anna", "role": "member"},
    )
    assert created.status_code == 200
    body = created.json()
    token = body["ingest_token"]
    emp_id = body["id"]
    assert token
    assert hash_ingest_token(token)

    now = datetime.now().astimezone()
    started = (now - timedelta(hours=1)).isoformat(timespec="seconds")
    ended = now.isoformat(timespec="seconds")

    bad = client.post(
        "/api/ingest/sessions",
        json={
            "hostname": "anna-pc",
            "sessions": [
                {
                    "app_name": "code.exe",
                    "started_at": started,
                    "ended_at": ended,
                    "duration_sec": 3600,
                    "category": "productive",
                    "ingest_key": "anna-pc:1",
                }
            ],
        },
        headers={"Authorization": "Bearer wrong-token"},
    )
    assert bad.status_code == 401

    ok = client.post(
        "/api/ingest/sessions",
        json={
            "hostname": "anna-pc",
            "sessions": [
                {
                    "app_name": "code.exe",
                    "window_title": "app",
                    "started_at": started,
                    "ended_at": ended,
                    "duration_sec": 3600,
                    "category": "productive",
                    "activity_label": "Coding",
                    "ingest_key": "anna-pc:1",
                }
            ],
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert ok.status_code == 200
    assert ok.json()["inserted"] == 1

    again = client.post(
        "/api/ingest/sessions",
        json={
            "hostname": "anna-pc",
            "sessions": [
                {
                    "app_name": "code.exe",
                    "started_at": started,
                    "ended_at": ended,
                    "duration_sec": 3600,
                    "category": "productive",
                    "ingest_key": "anna-pc:1",
                }
            ],
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert again.status_code == 200
    assert again.json()["skipped"] == 1

    team = client.get("/api/company/team")
    assert team.status_code == 200
    rows = team.json()
    anna = next(r for r in rows if r["id"] == emp_id)
    assert anna["total_sec"] >= 3500
    assert anna["focus_pct"] > 0

    filtered = client.get(f"/api/summary/today?employee_id={emp_id}")
    assert filtered.status_code == 200
    assert filtered.json()["total_sec"] >= 3500


def test_index_has_layered_reports_and_company_settings():
    from deskline.config import WEB_ROOT

    html = (WEB_ROOT / "templates" / "index.html").read_text(encoding="utf-8")
    assert 'id="teamGauges"' in html
    assert 'id="todayTimelineStrip"' in html
    assert 'id="companyModeToggle"' in html
    assert 'name="hub_url"' in html
    assert 'id="filterEmployeeToday"' in html
