from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

from deskline.classify import (
    display_name_for_app,
    extract_site_from_title,
    resolve_activity,
)
from deskline.db import Database


def test_extract_site_from_title_common_patterns():
    assert extract_site_from_title("Inbox - gmail.com", "chrome.exe") == "gmail.com"
    assert extract_site_from_title("Pull requests · github.com", "msedge.exe") == "github.com"
    assert extract_site_from_title("https://docs.python.org/3/", "firefox.exe") == "docs.python.org"
    assert extract_site_from_title("Document1 - Word", "winword.exe") is None
    assert extract_site_from_title("Cool video - YouTube", "msedge.exe") == "youtube.com"


def test_display_names():
    assert display_name_for_app("msedge.exe") == "Microsoft Edge"
    assert display_name_for_app("mstsc.exe") == "Remote Desktop"


def test_resolve_browser_youtube():
    meta = resolve_activity("msedge.exe", "Funny cats - YouTube", "youtube.com")
    assert meta["activity_label"] == "YouTube"
    assert meta["activity_kind"] == "video"
    assert meta["display_name"] == "Microsoft Edge"
    assert meta["category"] == "distracting"


def test_resolve_browser_email_and_messenger():
    assert resolve_activity("chrome.exe", "Inbox", "mail.yandex.ru")["activity_label"] == "Почта"
    assert resolve_activity("chrome.exe", "Chat", "web.telegram.org")["activity_kind"] == "messaging"


def test_resolve_desktop_apps():
    meta = resolve_activity("telegram.exe", "Chat with Ann")
    assert meta["activity_label"] == "Мессенджер"
    assert meta["display_name"] == "Telegram"
    rdp = resolve_activity("mstsc.exe", "user - remote")
    assert rdp["activity_kind"] == "remote"


def test_system_noise_hidden():
    meta = resolve_activity("lockapp.exe", "Lock")
    assert meta["hidden"] is True
    assert meta["activity_kind"] == "system"


def test_db_summary_uses_friendly_labels(tmp_path: Path):
    db = Database(tmp_path / "t.db")
    start = datetime.now().astimezone() - timedelta(minutes=40)
    sid = db.start_session(
        "msedge.exe",
        "Music - YouTube",
        "youtube.com",
        "distracting",
        started_at=start,
        display_name="Microsoft Edge",
        activity_kind="video",
        activity_label="YouTube",
    )
    db.end_session(sid, ended_at=start + timedelta(minutes=25))
    sid2 = db.start_session(
        "cursor.exe",
        "main.py",
        None,
        "productive",
        started_at=start + timedelta(minutes=25),
        display_name="Cursor",
        activity_kind="work",
        activity_label="Разработка",
    )
    db.end_session(sid2, ended_at=start + timedelta(minutes=40))

    summary = db.summary_for_day()
    names = [x["name"] for x in summary["by_activity"]]
    assert "YouTube" in names
    assert "Разработка" in names
    assert "msedge.exe" not in names
    app_names = [x["name"] for x in summary["by_app"]]
    assert "Microsoft Edge" in app_names
    assert "Cursor" in app_names
