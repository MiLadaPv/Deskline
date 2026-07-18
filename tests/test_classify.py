from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

from deskline.classify import classify, extract_site_from_title
from deskline.db import Database


def test_extract_site_from_title_common_patterns():
    assert extract_site_from_title("Inbox - gmail.com", "chrome.exe") == "gmail.com"
    assert extract_site_from_title("Pull requests · github.com", "msedge.exe") == "github.com"
    assert extract_site_from_title("https://docs.python.org/3/", "firefox.exe") == "docs.python.org"
    assert extract_site_from_title("Document1 - Word", "winword.exe") is None


def test_classify_defaults_and_overrides():
    assert classify("code.exe") == "productive"
    assert classify("chrome.exe", "youtube.com") == "distracting"
    assert classify("chrome.exe", "github.com") == "productive"
    assert classify("notepad.exe") == "neutral"
    assert classify("chrome.exe", "youtube.com", user_site_rules={"youtube.com": "productive"}) == "productive"
    assert classify("discord.exe", user_app_rules={"discord.exe": "neutral"}) == "neutral"


def test_db_session_lifecycle(tmp_path: Path):
    db = Database(tmp_path / "t.db")
    sid = db.start_session("code.exe", "main.py - Cursor", None, "productive")
    assert sid > 0
    open_row = db.open_session()
    assert open_row is not None
    assert open_row.app_name == "code.exe"
    db.end_session(sid)
    assert db.open_session() is None


def test_db_summary_and_rules(tmp_path: Path):
    db = Database(tmp_path / "t2.db")
    start = datetime.now().astimezone() - timedelta(minutes=30)
    sid = db.start_session("code.exe", "x", None, "productive", started_at=start)
    db.end_session(sid, ended_at=start + timedelta(minutes=20))
    sid2 = db.start_session("discord.exe", "friends", None, "distracting", started_at=start + timedelta(minutes=20))
    db.end_session(sid2, ended_at=start + timedelta(minutes=30))

    summary = db.summary_for_day()
    assert summary["total_sec"] >= 29 * 60
    assert summary["by_category"]["productive"] >= 19 * 60
    assert summary["by_app"][0]["name"] in {"code.exe", "discord.exe"}

    db.set_app_rule("discord.exe", "neutral")
    assert db.get_app_rules()["discord.exe"] == "neutral"

    db.add_screenshot(str(tmp_path / "a.jpg"), "interval", sid)
    shots = db.screenshots_for_date()
    assert len(shots) == 1
