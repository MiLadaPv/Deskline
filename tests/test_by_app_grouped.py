from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

from deskline.db import Database


def test_by_app_grouped_nests_browser_activities(tmp_path: Path):
    db = Database(tmp_path / "t.db")
    db.init_schema()
    start = datetime.now().astimezone().replace(hour=10, minute=0, second=0, microsecond=0)
    # Edge: two sites
    s1 = db.start_session(
        app_name="msedge.exe",
        window_title="ChatGPT",
        url_hint="chatgpt.com",
        category="productive",
        display_name="Microsoft Edge",
        activity_kind="work",
        activity_label="ChatGPT",
        app_path=r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        started_at=start,
    )
    db.end_session(s1, ended_at=start + timedelta(minutes=12))
    s2 = db.start_session(
        app_name="msedge.exe",
        window_title="Sber",
        url_hint="online.sberbank.ru",
        category="neutral",
        display_name="Microsoft Edge",
        activity_kind="other",
        activity_label="СберБанк Онлайн",
        app_path=r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        started_at=start + timedelta(minutes=12),
    )
    db.end_session(s2, ended_at=start + timedelta(minutes=14))
    # Telegram: single activity = parent name → no children
    s3 = db.start_session(
        app_name="telegram.exe",
        window_title="Telegram",
        url_hint=None,
        category="distracting",
        display_name="Telegram",
        activity_kind="messaging",
        activity_label="Telegram",
        started_at=start,
    )
    db.end_session(s3, ended_at=start + timedelta(minutes=11))

    summary = db.summary_range(start, start + timedelta(hours=2))
    grouped = summary["by_app_grouped"]
    assert grouped
    edge = next(g for g in grouped if g["name"] == "Microsoft Edge")
    assert edge["sec"] >= 60
    assert len(edge["children"]) >= 2
    child_names = {c["name"] for c in edge["children"]}
    assert "ChatGPT" in child_names
    tg = next(g for g in grouped if g["name"] == "Telegram")
    assert tg["children"] == []
