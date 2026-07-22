from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

from deskline.classify import normalize_category, resolve_activity
from deskline.db import Database


def test_normalize_category():
    assert normalize_category("unrated") == "unrated"
    assert normalize_category("PRODUCTIVE") == "productive"
    assert normalize_category("nope") == "neutral"


def test_unknown_desktop_app_is_unrated():
    meta = resolve_activity("weirdtool999.exe", "Weird")
    assert meta["category"] == "unrated"


def test_user_unrated_rule_overrides_default():
    meta = resolve_activity(
        "cursor.exe",
        "main.py",
        None,
        user_app_rules={"cursor.exe": "unrated"},
    )
    assert meta["category"] == "unrated"


def test_ratings_and_timeline(tmp_path: Path):
    db = Database(tmp_path / "r.db")
    start = datetime.now().astimezone() - timedelta(minutes=30)
    sid = db.start_session(
        "cursor.exe",
        "main.py",
        None,
        "productive",
        started_at=start,
        display_name="Cursor",
        activity_kind="work",
        activity_label="Разработка",
    )
    db.add_idle_seconds(sid, 120)
    db.end_session(sid, ended_at=start + timedelta(minutes=20))

    sid2 = db.start_session(
        "msedge.exe",
        "Cats - YouTube",
        "youtube.com",
        "distracting",
        started_at=start + timedelta(minutes=20),
        display_name="Microsoft Edge",
        activity_kind="video",
        activity_label="YouTube",
    )
    db.end_session(sid2, ended_at=start + timedelta(minutes=30))

    timeline = db.timeline_for_day()
    assert len(timeline) >= 2
    assert timeline[0]["name"] == "Cursor"
    assert timeline[0]["idle_sec"] >= 100

    ratings = db.ratings_for_day()
    keys = {r["key"] for r in ratings}
    assert "cursor.exe" in keys
    assert "youtube.com" in keys

    db.set_site_rule("youtube.com", "productive")
    ratings2 = db.ratings_for_day()
    yt = next(r for r in ratings2 if r["key"] == "youtube.com")
    assert yt["category"] == "productive"
    assert yt["user_override"] is True

    summary = db.summary_for_day()
    # unrated maps to neutral for focus; productive still from cursor + youtube override
    # note: summary uses stored session category, not live rules
    assert "focus_pct" in summary
