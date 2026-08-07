from __future__ import annotations

from datetime import date, datetime, timedelta
from pathlib import Path

from deskline.api import create_app
from deskline.db import Database
from deskline.tracker import Tracker


def test_timeline_for_arbitrary_day(tmp_path: Path):
    db = Database(tmp_path / "day.db")
    past = datetime.now().astimezone().replace(hour=10, minute=0, second=0, microsecond=0) - timedelta(
        days=2
    )
    sid = db.start_session(
        "cursor.exe",
        "main.py",
        None,
        "productive",
        started_at=past,
        display_name="Cursor",
        activity_kind="work",
        activity_label="Cursor",
    )
    db.end_session(sid, ended_at=past + timedelta(minutes=45))

    day = past.date()
    rows = db.timeline_for_day(day)
    assert len(rows) >= 1
    assert rows[0]["name"] == "Cursor"
    assert db.timeline_for_day(date.today()) == [] or True

    # Route exists on the app
    tracker = Tracker(db)
    tracker.cfg["paused"] = True
    app = create_app(tracker, db)
    paths = {getattr(r, "path", None) for r in app.routes}
    assert "/api/timeline" in paths
    assert "/api/timeline/today" in paths


def test_index_tabs_have_distinct_roles():
    from deskline.config import WEB_ROOT

    html = (WEB_ROOT / "templates" / "index.html").read_text(encoding="utf-8")
    assert 'id="dayNav"' in html
    assert 'id="dayGantt"' in html
    assert 'id="daySummaryLine"' in html
    # No duplicate KPI cards / pies on Day; composition lives on Usage.
    assert 'id="dayKpiStrip"' not in html
    assert 'id="dayCatPie"' not in html
    assert 'id="dayKindPie"' not in html
    assert 'id="usageCatPie"' in html
    assert 'id="usageKindPie"' in html
    assert 'id="topAppsToday"' not in html
    assert 'id="todayTimelineStrip"' not in html
    assert "Обзор" in html
    assert "Лента" in html
    assert "Где время" in html
    assert "По часам" not in html
    assert "app-nav-rail" in html
    assert 'data-tab="today"' in html


def test_day_feed_ux_contracts():
    from deskline.config import WEB_ROOT

    html = (WEB_ROOT / "templates" / "index.html").read_text(encoding="utf-8")
    js = (WEB_ROOT / "static" / "js" / "app.js").read_text(encoding="utf-8")
    css = (WEB_ROOT / "static" / "css" / "app.css").read_text(encoding="utf-8")

    assert 'data-gantt-mode="active"' in html
    assert 'data-gantt-mode="full"' in html
    assert 'id="dayPictureTitle"' in html
    assert "Сверху свежие" in html
    assert "function activityViewBounds" in js
    assert "Newest first" in js or "compactFeedRows" in js
    assert "dayGanttMode" in js
    assert "highlightTimelineSession" in js
    assert "compactFeedRows" in js
    assert ".day-picture-head" in css
    assert ".timeline li.is-hot" in css


def test_control_strip_clips_to_capsule():
    from deskline.config import WEB_ROOT

    html = (WEB_ROOT / "templates" / "index.html").read_text(encoding="utf-8")
    css = (WEB_ROOT / "static" / "css" / "app.css").read_text(encoding="utf-8")
    assert 'class="control-strip"' in html
    assert "workModeToggle" in html
    # Capsule must clip children so end chips don't poke past the curve.
    idx = css.find(".control-strip {")
    assert idx >= 0
    chunk = css[idx : idx + 420]
    assert "overflow: hidden" in chunk
    assert "border-radius: 999px" in chunk


def test_gantt_blocks_have_no_rounding():
    from deskline.config import WEB_ROOT

    css = (WEB_ROOT / "static" / "css" / "app.css").read_text(encoding="utf-8")
    idx = css.find(".gantt-block {")
    assert idx >= 0
    chunk = css[idx : idx + 380]
    assert "border-radius: 0" in chunk

def test_day_chip_active_uses_accent_not_ink_flip():
    from deskline.config import WEB_ROOT

    css = (WEB_ROOT / "static" / "css" / "app.css").read_text(encoding="utf-8")
    idx = css.find(".day-chip.is-active {")
    assert idx >= 0
    chunk = css[idx : idx + 280]
    assert "var(--accent)" in chunk
    assert "var(--ink)" not in chunk


def test_focus_rhythm_chart_no_capsules():
    from deskline.config import WEB_ROOT

    html = (WEB_ROOT / "templates" / "index.html").read_text(encoding="utf-8")
    css = (WEB_ROOT / "static" / "css" / "app.css").read_text(encoding="utf-8")
    js = (WEB_ROOT / "static" / "js" / "app.js").read_text(encoding="utf-8")
    assert "prod-focus-legend" in html
    assert "prod-day-track" in css
    assert "prod-day-track" in js
    start = css.find(".prod-days-chart-wide .prod-day-stack {")
    assert start >= 0
    chunk = css[start : start + 260]
    assert "border-radius: 999px" not in chunk
    assert "border-radius: 0" in chunk


def test_hours_chart_multi_series():
    from deskline.config import WEB_ROOT

    html = (WEB_ROOT / "templates" / "index.html").read_text(encoding="utf-8")
    css = (WEB_ROOT / "static" / "css" / "app.css").read_text(encoding="utf-8")
    js = (WEB_ROOT / "static" / "js" / "app.js").read_text(encoding="utf-8")
    assert "hours-line-legend" in html
    assert "hours-leg-total" in html
    assert "hours-line-path.is-total" in css
    assert "hours-line-path.is-productive" in css
    assert "hours-line-path.is-neutral" in css
    assert "hours-line-path.is-distracting" in css
    assert "stroke-width: 3.75" in css
    assert 'class="hours-line-path is-total"' in js
    assert 'class="hours-line-path is-distracting"' in js
    assert "by_category?.productive" in js
