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
    assert display_name_for_app("windowsterminal.exe") == "Терминал"
    assert display_name_for_app("snippingtool.exe") == "Ножницы"
    assert display_name_for_app("notepad.exe") == "Блокнот"
    assert display_name_for_app("keepass.exe") == "KeePass"


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


def test_system_noise_hidden():
    meta = resolve_activity("lockapp.exe", "Lock")
    assert meta["hidden"] is True
    assert meta["activity_kind"] == "system"


def test_rdp_client_hidden_from_rankings():
    for exe in ("mstsc.exe", "msrdc.exe", "rdpclip.exe"):
        meta = resolve_activity(exe, "Remote Desktop Connection")
        assert meta["hidden"] is True
        assert meta["activity_kind"] == "system"


def test_credential_and_script_noise_hidden():
    assert resolve_activity("CredentialUIBroker.exe", "Windows Security")["hidden"] is True
    assert resolve_activity("url.py", "url.py")["hidden"] is True
    assert resolve_activity("script.pyw", "script")["hidden"] is True


def test_db_summary_excludes_rdp_client(tmp_path: Path):
    db = Database(tmp_path / "rdp.db")
    start = datetime.now().astimezone() - timedelta(minutes=30)
    sid = db.start_session(
        "mstsc.exe",
        "server - Remote Desktop Connection",
        None,
        "productive",
        started_at=start,
        display_name="Remote Desktop",
        activity_kind="system",
        activity_label="Система",
    )
    db.end_session(sid, ended_at=start + timedelta(minutes=20))
    sid2 = db.start_session(
        "cursor.exe",
        "main.py",
        None,
        "productive",
        started_at=start + timedelta(minutes=20),
        display_name="Cursor",
        activity_kind="work",
        activity_label="Разработка",
    )
    db.end_session(sid2, ended_at=start + timedelta(minutes=30))

    summary = db.summary_for_day()
    activity_names = [x["name"] for x in summary["by_activity"]]
    app_names = [x["name"] for x in summary["by_app"]]
    assert "Remote Desktop" not in activity_names
    assert "Удалённый рабочий стол" not in activity_names
    assert "mstsc.exe" not in activity_names
    assert "Remote Desktop" not in app_names
    assert "Разработка" in activity_names
    assert "Cursor" in app_names


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


def test_db_summary_hides_sub_minute_entries(tmp_path: Path):
    db = Database(tmp_path / "short.db")
    start = datetime.now().astimezone() - timedelta(minutes=5)
    sid = db.start_session(
        "snippingtool.exe",
        "Snipping Tool",
        None,
        "neutral",
        started_at=start,
        display_name="Ножницы",
        activity_kind="other",
        activity_label="Ножницы",
    )
    db.end_session(sid, ended_at=start + timedelta(seconds=20))
    sid2 = db.start_session(
        "cursor.exe",
        "main.py",
        None,
        "productive",
        started_at=start + timedelta(seconds=20),
        display_name="Cursor",
        activity_kind="work",
        activity_label="Разработка",
    )
    db.end_session(sid2, ended_at=start + timedelta(minutes=5))

    summary = db.summary_for_day()
    names = [x["name"] for x in summary["by_activity"]]
    assert "Ножницы" not in names
    assert "Разработка" in names
    assert all(x["sec"] >= 60 for x in summary["by_activity"])
    assert all(x["sec"] >= 60 for x in summary["by_app"])
