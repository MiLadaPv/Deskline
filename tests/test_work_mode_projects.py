from __future__ import annotations

from datetime import date, datetime, timedelta
from pathlib import Path

from deskline.classify import resolve_activity
from deskline.config import load_config, save_config
from deskline.db import Database


def test_messenger_default_neutral_without_work_mode():
    meta = resolve_activity(
        "msedge.exe",
        "Chat — messenger.yandex.ru",
        "messenger.yandex.ru",
        work_mode=False,
    )
    assert meta["activity_kind"] == "messaging"
    assert meta["category"] == "neutral"

    tg = resolve_activity(
        "chrome.exe",
        "Telegram Web",
        "web.telegram.org",
        work_mode=False,
    )
    assert tg["category"] == "neutral"


def test_messenger_productive_in_work_mode():
    meta = resolve_activity(
        "msedge.exe",
        "Chat — messenger.yandex.ru",
        "messenger.yandex.ru",
        work_mode=True,
    )
    assert meta["category"] == "productive"

    desk = resolve_activity("telegram.exe", "Alice", work_mode=True)
    assert desk["activity_kind"] == "messaging"
    assert desk["category"] == "productive"


def test_work_chat_keywords_force_productive_outside_work_mode():
    meta = resolve_activity(
        "msedge.exe",
        "RG-Soft standup — Discord",
        "discord.com",
        work_mode=False,
        work_chat_keywords=["rg-soft", "standup"],
    )
    assert meta["category"] == "productive"


def test_user_override_beats_work_mode():
    meta = resolve_activity(
        "msedge.exe",
        "Chat",
        "messenger.yandex.ru",
        user_site_rules={"messenger.yandex.ru": "distracting"},
        work_mode=True,
    )
    assert meta["category"] == "distracting"


def test_projects_focus_and_summary_filter(tmp_path: Path, monkeypatch):
    data = tmp_path / "Deskline"
    monkeypatch.setattr("deskline.config.DATA_ROOT", data)
    monkeypatch.setattr("deskline.config.DB_PATH", data / "deskline.db")
    monkeypatch.setattr("deskline.config.SCREENSHOTS_DIR", data / "screenshots")
    monkeypatch.setattr("deskline.config.ICONS_DIR", data / "icons")
    monkeypatch.setattr("deskline.config.CONFIG_PATH", data / "config.json")
    data.mkdir(parents=True)
    (data / "screenshots").mkdir()
    (data / "icons").mkdir()

    db = Database(data / "deskline.db")
    proj = db.create_project("Клиент A", "#1f6b56")
    defaults = db.list_tasks(proj["id"])
    assert any(t["name"] == "Основная" for t in defaults)
    task = db.create_task(proj["id"], "Отчёт")
    assert proj["id"]
    assert task["project_id"] == proj["id"]

    cfg = load_config()
    cfg["current_project_id"] = proj["id"]
    cfg["current_task_id"] = task["id"]
    cfg["work_mode"] = True
    save_config(cfg)
    assert load_config()["current_project_id"] == proj["id"]

    start = datetime.now().astimezone() - timedelta(minutes=20)
    end = start + timedelta(minutes=10)
    sid = db.start_session(
        app_name="code.exe",
        window_title="app.py",
        url_hint=None,
        category="productive",
        display_name="VS Code",
        activity_kind="work",
        activity_label="VS Code",
        project_id=proj["id"],
        task_id=task["id"],
        started_at=start,
    )
    db.end_session(sid, ended_at=end)

    other = db.start_session(
        app_name="notepad.exe",
        window_title="notes",
        url_hint=None,
        category="neutral",
        display_name="Блокнот",
        activity_kind="other",
        activity_label="Блокнот",
        project_id=None,
        started_at=start,
    )
    db.end_session(other, ended_at=end)

    full = db.summary_for_day()
    assert any(p["project_id"] == proj["id"] for p in full["by_project"])
    filtered = db.summary_for_day(project_id=proj["id"])
    assert filtered["total_sec"] >= 9 * 60
    assert filtered["total_sec"] < full["total_sec"]


def test_daily_trends_shape(tmp_path: Path, monkeypatch):
    data = tmp_path / "Deskline"
    monkeypatch.setattr("deskline.config.DATA_ROOT", data)
    monkeypatch.setattr("deskline.config.DB_PATH", data / "deskline.db")
    monkeypatch.setattr("deskline.config.SCREENSHOTS_DIR", data / "screenshots")
    monkeypatch.setattr("deskline.config.ICONS_DIR", data / "icons")
    monkeypatch.setattr("deskline.config.CONFIG_PATH", data / "config.json")
    data.mkdir(parents=True)
    (data / "screenshots").mkdir()
    (data / "icons").mkdir()

    db = Database(data / "deskline.db")
    start = datetime.now().astimezone() - timedelta(hours=2)
    end = start + timedelta(hours=1)
    sid = db.start_session(
        app_name="code.exe",
        window_title="x",
        url_hint=None,
        category="productive",
        display_name="VS Code",
        activity_kind="work",
        activity_label="VS Code",
        started_at=start,
    )
    db.end_session(sid, ended_at=end)

    trends = db.daily_trends(days=7)
    assert len(trends) == 7
    assert trends[-1]["day"] == date.today().isoformat()
    assert "by_category" in trends[-1]
    assert trends[-1]["total_sec"] >= 3500


def test_screenshot_flag_distracting_only_in_work_mode(tmp_path: Path, monkeypatch):
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
    path = shots / "a.jpg"
    path.write_bytes(b"jpg")
    db.add_screenshot(str(path), reason="interval", session_id=sid)

    cfg = load_config()
    cfg["work_mode"] = False
    save_config(cfg)
    rows = db.screenshots_for_date()
    assert rows and rows[0]["flag_distracting"] is False

    cfg["work_mode"] = True
    save_config(cfg)
    rows = db.screenshots_for_date()
    assert rows[0]["flag_distracting"] is True
    assert rows[0]["category"] == "distracting"
