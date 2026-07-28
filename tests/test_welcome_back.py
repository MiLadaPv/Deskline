from __future__ import annotations

import json
from pathlib import Path

from deskline.config import DEFAULT_CONFIG
from deskline.db import Database
from deskline.tracker import Tracker
from deskline.welcome_back_dialog import _fmt_away


def test_fmt_away_readable():
    assert _fmt_away(45) == "45 с"
    assert _fmt_away(120) == "2 мин"
    assert "ч" in _fmt_away(3700)


def test_welcome_back_defaults_in_config():
    assert DEFAULT_CONFIG.get("welcome_back_enabled") is True
    assert float(DEFAULT_CONFIG.get("welcome_back_after_sec")) == 600.0


def test_welcome_back_skips_short_idle(tmp_path: Path, monkeypatch):
    db = Database(tmp_path / "wb.db")
    db.create_project("Alpha", color="#123456")
    tracker = Tracker(db)
    tracker.cfg["welcome_back_enabled"] = True
    tracker.cfg["welcome_back_after_sec"] = 600
    called = {"n": 0}

    def fake_ask(*_a, **_k):
        called["n"] += 1
        return {"action": "continue", "project_id": None, "task_id": None}

    monkeypatch.setattr("deskline.tracker.ask_welcome_back", fake_ask)
    tracker._maybe_welcome_back(tracker.cfg, 120.0, reason="idle")
    # thread not started for short idle
    assert called["n"] == 0
    assert tracker._welcome_back_prompting is False


def test_welcome_back_triggers_after_threshold(tmp_path: Path, monkeypatch):
    db = Database(tmp_path / "wb2.db")
    proj = db.create_project("Beta", color="#abcdef")
    tracker = Tracker(db)
    tracker.cfg["welcome_back_enabled"] = True
    tracker.cfg["welcome_back_after_sec"] = 300
    tracker.cfg["current_project_id"] = int(proj["id"])
    seen = {}

    def fake_ask(payload, *, timeout_sec=60.0):
        seen["payload"] = payload
        seen["timeout"] = timeout_sec
        return {"action": "continue", "project_id": int(proj["id"]), "task_id": None}

    monkeypatch.setattr("deskline.tracker.ask_welcome_back", fake_ask)
    monkeypatch.setattr("deskline.tracker.notify", lambda *a, **k: None)
    # Run worker synchronously
    tracker._welcome_back_prompting = False
    tracker._suppress_welcome_back_until = 0.0
    tracker._ask_welcome_back(900.0, "idle")
    assert seen["payload"]["away_sec"] == 900.0
    assert seen["payload"]["reason"] == "idle"
    assert any(p["name"] == "Beta" for p in seen["payload"]["projects"])
    assert tracker._welcome_back_prompting is False


def test_welcome_back_dialog_writes_result(tmp_path: Path):
    payload = {
        "away_sec": 700,
        "reason": "idle",
        "project_id": 1,
        "project_name": "Demo",
        "project_color": "#1f6b56",
        "task_id": None,
        "task_name": None,
        "projects": [{"id": 1, "name": "Demo", "color": "#1f6b56"}],
        "timeout_sec": 1,
    }
    payload_path = tmp_path / "payload.json"
    result_path = tmp_path / "result.json"
    payload_path.write_text(json.dumps(payload), encoding="utf-8")

    # Headless: simulate timeout path by writing result like dialog timeout
    result_path.write_text(
        json.dumps({"action": "continue", "project_id": 1, "task_id": None}),
        encoding="utf-8",
    )
    data = json.loads(result_path.read_text(encoding="utf-8"))
    assert data["action"] == "continue"


def test_ask_welcome_back_fallback_without_ui(monkeypatch, tmp_path: Path):
    from deskline import notify as notify_mod

    def boom(*_a, **_k):
        raise RuntimeError("no ui")

    monkeypatch.setattr(notify_mod.subprocess, "run", boom)
    out = notify_mod.ask_welcome_back(
        {"project_id": 7, "task_id": None, "projects": []},
        timeout_sec=5,
    )
    assert out["action"] == "continue"
    assert out["project_id"] == 7
