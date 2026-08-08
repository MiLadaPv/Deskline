from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

from fastapi.testclient import TestClient

from deskline.classify import resolve_activity
from deskline.config import DEFAULT_CONFIG, save_config
from deskline.db import Database
from deskline.meetings import (
    build_meetings_report,
    infer_meeting_site,
    is_email_activity,
    is_meeting_activity,
    is_meeting_app,
    is_meeting_site,
    meeting_app_label,
    meeting_context_from_title,
    meeting_site_label,
)


def test_meeting_allowlist_helpers():
    assert is_meeting_app("Teams.exe")
    assert is_meeting_app(r"C:\Program Files\Zoom\bin\Zoom.exe")
    assert not is_meeting_app("chrome.exe")
    assert is_meeting_site("meet.google.com")
    assert is_meeting_site("www.zoom.us")
    assert is_meeting_site("us05web.zoom.us")
    assert not is_meeting_site("messenger.yandex.ru")  # chat-first, not auto-call
    assert is_meeting_site("telemost.yandex.ru")
    assert not is_meeting_site("telegram.org")
    assert meeting_app_label("zoom.exe") == "Zoom"
    assert meeting_site_label("messenger.yandex.ru") == "Яндекс Мессенджер"
    assert meeting_site_label("telemost.yandex.ru") == "Яндекс Телемост"


def test_telemost_and_messenger_title_inference():
    assert resolve_activity("msedge.exe", "Звонок в Яндекс Телемосте")["url_hint"] == "telemost.yandex.ru"
    assert resolve_activity("msedge.exe", "Звонок в Яндекс Телемосте")["activity_label"] == "Яндекс Телемост"
    assert (
        infer_meeting_site(activity_label="Звонок в Яндекс Телемосте", window_title=None)
        == "telemost.yandex.ru"
    )
    assert is_meeting_activity(
        app_name="msedge.exe",
        site=None,
        activity_label="Звонок в Яндекс Телемосте",
        window_title="",
    )
    # Passive Messenger chat must NOT count as a call.
    assert not is_meeting_activity(
        app_name="msedge.exe",
        site="messenger.yandex.ru",
        activity_label="Яндекс Мессенджер",
        window_title="Яндекс Мессенджер — 16 новых сообщений — Личный: Microsoft Edge",
    )
    # Explicit call signal in Messenger title still counts.
    assert is_meeting_activity(
        app_name="msedge.exe",
        site="messenger.yandex.ru",
        activity_label="Яндекс Мессенджер",
        window_title="Звонок — Яндекс Мессенджер — Microsoft Edge",
    )
    assert is_email_activity(site="mail.yandex.ru", activity_kind="email")
    assert is_email_activity(activity_label="Яндекс Почта")


def test_meeting_context_from_title_strips_noise():
    detail = meeting_context_from_title(
        "Яндекс Мессенджер — Команда Проект — Личный: Microsoft Edge",
        site="messenger.yandex.ru",
        activity_label="Яндекс Мессенджер",
    )
    assert detail == "Команда Проект"
    assert (
        meeting_context_from_title(
            "Яндекс Мессенджер — 16 новых сообщений — Личный: Microsoft Edge",
            site="messenger.yandex.ru",
        )
        is None
    )


def test_meeting_peers_from_titles():
    from deskline.meetings import meeting_peers_from_title

    assert meeting_peers_from_title(
        "Zoom Meeting with Alice, Bob — Google Chrome", site="zoom.us"
    ) == ["Alice", "Bob"]
    assert meeting_peers_from_title(
        "Звонок в Яндекс Телемосте — Команда Проект — Личный: Microsoft Edge"
    ) == ["Команда Проект"]
    assert (
        meeting_peers_from_title(
            "Яндекс Мессенджер — 10 новых сообщений и еще 9 страниц — Личный: Microsoft Edge"
        )
        == []
    )


def test_attach_peers_to_channels_marks_messenger_hint():
    from deskline.meetings import attach_peers_to_channels

    channels = attach_peers_to_channels(
        [{"key": "site:messenger.yandex.ru", "name": "Яндекс Мессенджер", "sec": 100}],
        [
            {
                "site": "messenger.yandex.ru",
                "sec": 100,
                "window_title": "Яндекс Мессенджер — 3 новых сообщения и еще 8 страниц — Личный: Microsoft Edge",
            }
        ],
    )
    assert channels[0]["has_peers"] is False
    assert "Edge" in (channels[0].get("peers_hint") or "")

    with_peers = attach_peers_to_channels(
        [{"key": "site:telemost.yandex.ru", "name": "Яндекс Телемост", "sec": 50}],
        [
            {
                "site": "telemost.yandex.ru",
                "sec": 20,
                "window_title": "Звонок в Яндекс Телемосте — Анна, Иван — Личный: Microsoft Edge",
            },
            {
                "site": "telemost.yandex.ru",
                "sec": 30,
                "window_title": "Звонок в Яндекс Телемосте — Команда Проект — Личный: Microsoft Edge",
            },
        ],
    )
    assert with_peers[0]["has_peers"] is True
    names = {p["name"] for p in with_peers[0]["peers"]}
    assert "Анна, Иван" in names or "Анна" in str(names)
    assert "Команда Проект" in names


def test_compact_meeting_sessions_absorbs_messenger_flicker():
    from deskline.meetings import compact_meeting_sessions

    base = "2026-08-07T19:40:00+03:00"
    rows = []
    t = 0
    for sec in (8, 13, 4, 37, 3, 7, 6, 120):
        start_m = 40 + t // 60
        start_s = t % 60
        end = t + sec
        end_m = 40 + end // 60
        end_s = end % 60
        rows.append(
            {
                "started_at": f"2026-08-07T19:{start_m:02d}:{start_s:02d}+03:00",
                "ended_at": f"2026-08-07T19:{end_m:02d}:{end_s:02d}+03:00",
                "sec": sec,
                "name": "Яндекс Мессенджер",
                "site": "messenger.yandex.ru",
                "app_name": "msedge.exe",
            }
        )
        t = end
    compact = compact_meeting_sessions(rows, min_sec=60, max_gap_sec=180)
    assert len(compact) <= 2
    assert sum(r["sec"] for r in compact) == sum(r["sec"] for r in rows)


def test_build_meetings_report_filters_and_totals():
    report = build_meetings_report(
        by_app=[
            {"app_name": "zoom.exe", "name": "Zoom", "sec": 600},
            {"app_name": "chrome.exe", "name": "Chrome", "sec": 900},
        ],
        by_site=[
            {"name": "meet.google.com", "sec": 300},
            {"name": "messenger.yandex.ru", "sec": 120},
            {"name": "youtube.com", "sec": 120},
        ],
        sessions=[
            {
                "started_at": "2026-07-22T10:00:00+00:00",
                "ended_at": "2026-07-22T10:10:00+00:00",
                "sec": 600,
                "app_name": "zoom.exe",
                "name": "Zoom",
            },
            {
                "started_at": "2026-07-22T11:00:00+00:00",
                "ended_at": "2026-07-22T11:05:00+00:00",
                "sec": 300,
                "app_name": "msedge.exe",
                "site": "meet.google.com",
                "name": "Google Meet",
            },
            {
                "started_at": "2026-07-22T12:00:00+00:00",
                "sec": 100,
                "app_name": "notepad.exe",
                "name": "Notepad",
            },
        ],
        email_channels=[{"key": "site:mail.yandex.ru", "name": "Яндекс Почта", "sec": 90}],
        email_sessions=[],
        total_tracked_sec=1800,
    )
    assert report["total_sec"] == 900.0
    assert report["share_pct"] == 50.0
    assert len(report["by_app"]) == 1
    assert len(report["by_site"]) == 1
    assert report["by_site"][0]["name"] in {"meet.google.com", "Google Meet"}
    assert len(report["sessions"]) == 2
    assert report["email_total_sec"] == 90.0
    assert "телемост" in report["note"].casefold() or "мессенджер" in report["note"].casefold()


def test_meetings_for_range_counts_yandex_and_mail(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("deskline.config.CONFIG_PATH", tmp_path / "config.json")
    monkeypatch.setattr("deskline.config.DATA_ROOT", tmp_path)
    monkeypatch.setattr("deskline.config.DB_PATH", tmp_path / "deskline.db")
    save_config({**DEFAULT_CONFIG, "work_mode": False})

    db = Database(tmp_path / "deskline.db")
    now = datetime.now().astimezone()
    start = now - timedelta(hours=2)
    end = now

    sid_zoom = db.start_session(
        "zoom.exe",
        "Zoom Meeting",
        None,
        "productive",
        display_name="Zoom",
        activity_kind="messaging",
        activity_label="Zoom",
        started_at=start,
    )
    db.end_session(sid_zoom, ended_at=start + timedelta(minutes=20))

    sid_msg = db.start_session(
        "msedge.exe",
        "Яндекс Мессенджер — 3 новых сообщения — Личный: Microsoft Edge",
        "messenger.yandex.ru",
        "neutral",
        display_name="Microsoft Edge",
        activity_kind="messaging",
        activity_label="Яндекс Мессенджер",
        started_at=start + timedelta(minutes=25),
    )
    db.end_session(sid_msg, ended_at=start + timedelta(minutes=40))

    sid_tm = db.start_session(
        "msedge.exe",
        "Звонок в Яндекс Телемосте — Личный: Microsoft Edge",
        None,
        "productive",
        display_name="Microsoft Edge",
        activity_kind="other",
        activity_label="Звонок в Яндекс Телемосте",
        started_at=start + timedelta(minutes=45),
    )
    db.end_session(sid_tm, ended_at=start + timedelta(minutes=55))

    sid_mail = db.start_session(
        "msedge.exe",
        "Входящие — Яндекс Почта — Личный: Microsoft Edge",
        "mail.yandex.ru",
        "productive",
        display_name="Microsoft Edge",
        activity_kind="email",
        activity_label="Яндекс Почта",
        started_at=start + timedelta(minutes=56),
    )
    db.end_session(sid_mail, ended_at=start + timedelta(minutes=66))

    report = db.meetings_for_range(start, end)
    # Zoom 20m + Telemost 10m — Messenger chat must not inflate calls.
    assert report["total_sec"] >= 28 * 60
    assert report["total_sec"] < 40 * 60
    sites = {r.get("site") for r in report["by_site"]}
    assert "messenger.yandex.ru" not in sites
    assert "telemost.yandex.ru" in sites
    assert report["email_total_sec"] >= 9 * 60
    assert any(r["name"] == "Яндекс Почта" for r in report["email_top"])


def test_meetings_api(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("deskline.config.CONFIG_PATH", tmp_path / "config.json")
    monkeypatch.setattr("deskline.config.DATA_ROOT", tmp_path)
    monkeypatch.setattr("deskline.config.DB_PATH", tmp_path / "deskline.db")
    monkeypatch.setattr("deskline.config.SCREENSHOTS_DIR", tmp_path / "shots")
    monkeypatch.setattr("deskline.auth.AUTH_PATH", tmp_path / "auth.json")
    save_config({**DEFAULT_CONFIG, "work_mode": False})

    from deskline.api import create_app
    from deskline.auth import set_password
    from deskline.tracker import Tracker

    set_password("test-pass-1234")
    db = Database(tmp_path / "deskline.db")
    tracker = Tracker(db)
    tracker.cfg["paused"] = True
    now = datetime.now().astimezone()
    sid = db.start_session(
        "teams.exe",
        "Standup",
        None,
        "productive",
        display_name="Microsoft Teams",
        activity_kind="messaging",
        activity_label="Microsoft Teams",
        started_at=now - timedelta(minutes=30),
    )
    db.end_session(sid, ended_at=now - timedelta(minutes=10))

    app = create_app(tracker, db)
    client = TestClient(app)
    client.post(
        "/api/auth/login",
        json={"username": "owner", "password": "test-pass-1234", "remember": False},
    )
    res = client.get("/api/meetings?period=today")
    assert res.status_code == 200
    body = res.json()
    assert body["total_sec"] >= 15 * 60
    assert any(r["app_name"] == "teams.exe" for r in body["by_app"])
    assert "email_total_sec" in body
    assert "meetingsEmailList" in (
        Path(__file__).resolve().parents[1] / "web" / "templates" / "index.html"
    ).read_text(encoding="utf-8")


def test_meetings_ui_no_rank_grid_overlap_and_grouped_sessions():
    from deskline.config import WEB_ROOT

    html = (WEB_ROOT / "templates" / "index.html").read_text(encoding="utf-8")
    css = (WEB_ROOT / "static" / "css" / "app.css").read_text(encoding="utf-8")
    js = (WEB_ROOT / "static" / "js" / "app.js").read_text(encoding="utf-8")
    assert 'class="rank-list meetings-channel-list"' in html
    assert 'id="meetingsSessions"' in html
    assert "session-groups" in html
    assert "li.meeting-channel" in css
    assert "flex-direction: column" in css
    assert "meeting-channel-main > .meeting-expand" in css
    assert "meetingSessionGroupHtml" in js
    assert "groupFeedByApp(compactFeedRows(report.sessions" in js
    assert "meeting-peers-shot" in js
    assert "/api/meetings/peers-from-shot" in js
    assert "Встречи / звонки" in js


def test_meetings_peers_vision_helpers():
    from deskline.meetings_vision import _shot_matches_channel, extract_peers_from_screenshot

    assert _shot_matches_channel(
        {"activity_label": "Яндекс Мессенджер", "window_title": "x"},
        "site:messenger.yandex.ru",
    )
    assert not _shot_matches_channel(
        {"activity_label": "Cursor", "window_title": "a.py"},
        "site:messenger.yandex.ru",
    )
    missing = extract_peers_from_screenshot({}, "/no/such/file.jpg")
    assert missing["ok"] is False
    assert missing["error"] == "screenshot_missing"
