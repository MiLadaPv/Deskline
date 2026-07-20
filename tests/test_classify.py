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


def test_extract_site_from_edge_multitab_titles():
    habr = extract_site_from_title(
        "Джейлбрейкаем чатботы: ChatGPT без фильтров / Хабр и еще 28 страниц — Личный: Microsoft Edge",
        "msedge.exe",
    )
    assert habr == "habr.com"
    yt = extract_site_from_title(
        "(106) 30 MIN BURPEE HIIT CHALLENGE - YouTube — Личный: Microsoft Edge",
        "msedge.exe",
    )
    assert yt == "youtube.com"


def test_browser_activity_not_generic_browser():
    meta = resolve_activity(
        "msedge.exe",
        "Джейлбрейкаем чатботы / Хабр и еще 28 страниц — Личный: Microsoft Edge",
    )
    assert meta["activity_label"] == "Habr"
    assert meta["activity_label"] != "Браузер"

    yt = resolve_activity(
        "msedge.exe",
        "(106) Workout - YouTube и еще 2 страницы — Личный: Microsoft Edge",
    )
    assert yt["activity_label"] == "YouTube"

    page = resolve_activity(
        "msedge.exe",
        "Курсы по квантовой физике и еще 37 страниц — Личный: Microsoft Edge",
    )
    assert page["activity_label"] != "Браузер"
    assert "Курсы по квантовой физике" in page["activity_label"]


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


def test_yandex_messenger_groups_unread_titles():
    a = resolve_activity(
        "msedge.exe",
        "Яндекс Мессенджер — 16 новых сообщений — Личный: Microsoft Edge",
    )
    b = resolve_activity(
        "msedge.exe",
        "Яндекс Мессенджер — 3 новых сообщения — Личный: Microsoft Edge",
    )
    c = resolve_activity(
        "msedge.exe",
        "Яндекс Мессенджер — 1 новое сообщение — Личный: Microsoft Edge",
    )
    assert a["activity_label"] == "Яндекс Мессенджер"
    assert b["activity_label"] == "Яндекс Мессенджер"
    assert c["activity_label"] == "Яндекс Мессенджер"
    assert a["activity_kind"] == "messaging"
    assert a["url_hint"] == "messenger.yandex.ru"


def test_yandex_messenger_real_nbsp_edge_title():
    """Exact pattern observed in production DB (NBSP + multi-tab + ZWSP in Edge)."""
    title = (
        "Яндекс\xa0Мессенджер\xa0— 18 новых сообщений и еще 32 страницы "
        "— Личный: Microsoft\u200b Edge"
    )
    meta = resolve_activity("msedge.exe", title)
    assert meta["activity_label"] == "Яндекс Мессенджер"
    assert meta["url_hint"] == "messenger.yandex.ru"

    other = resolve_activity(
        "msedge.exe",
        "Яндекс\xa0Мессенджер\xa0— 3 новых сообщения и еще 10 страниц "
        "— Личный: Microsoft\u200b Edge",
    )
    assert other["activity_label"] == meta["activity_label"]


def test_yandex_mail_groups_inbox_counter():
    meta = resolve_activity(
        "msedge.exe",
        "36 · Входящие — Яндекс Почта и еще 2 страницы — Личный: Microsoft Edge",
    )
    assert meta["activity_label"] == "Почта"
    assert meta["url_hint"] == "mail.yandex.ru"
    assert meta["activity_kind"] == "email"


def test_normalize_dynamic_title_strips_counters():
    from deskline.classify import normalize_dynamic_title

    assert normalize_dynamic_title("Яндекс Мессенджер — 16 новых сообщений") == "Яндекс Мессенджер"
    assert normalize_dynamic_title("Inbox (3)") == "Inbox"
    assert normalize_dynamic_title("(106) Workout - YouTube") == "Workout - YouTube"
    assert normalize_dynamic_title("36 · Входящие — Яндекс Почта") == "Входящие — Яндекс Почта"


def test_site_for_activity_label():
    from deskline.classify import site_for_activity_label

    assert site_for_activity_label("Habr") == "habr.com"
    assert site_for_activity_label("Яндекс Мессенджер") == "messenger.yandex.ru"
    assert site_for_activity_label("Почта") in {
        "gmail.com",
        "mail.google.com",
        "mail.yandex.ru",
        "mail.ru",
        "outlook.live.com",
        "outlook.office.com",
    }


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


def test_db_summary_groups_yandex_messenger_and_site_icon(tmp_path: Path):
    db = Database(tmp_path / "msg.db")
    start = datetime.now().astimezone() - timedelta(minutes=30)
    titles = [
        "Яндекс\xa0Мессенджер\xa0— 16 новых сообщений и еще 2 страницы — Личный: Microsoft\u200b Edge",
        "Яндекс\xa0Мессенджер\xa0— 3 новых сообщения и еще 2 страницы — Личный: Microsoft\u200b Edge",
    ]
    t0 = start
    for i, title in enumerate(titles):
        sid = db.start_session(
            "msedge.exe",
            title,
            None,
            "distracting",
            started_at=t0,
            display_name="Microsoft Edge",
            activity_kind="other",
            activity_label=f"Яндекс Мессенджер — {16 if i == 0 else 3} новых сообщений",
        )
        db.end_session(sid, ended_at=t0 + timedelta(minutes=10))
        t0 = t0 + timedelta(minutes=10)

    summary = db.summary_for_day()
    messenger = [x for x in summary["by_activity"] if "ессенджер" in x["name"]]
    assert len(messenger) == 1
    assert messenger[0]["name"] == "Яндекс Мессенджер"
    assert messenger[0]["sec"] >= 60
    assert messenger[0]["icon_url"].startswith("/media/icons/site_")
    assert "новых сообщен" not in messenger[0]["name"]


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
