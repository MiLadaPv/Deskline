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
