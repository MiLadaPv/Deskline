from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / "web" / "templates" / "index.html").read_text(encoding="utf-8")
JS = (ROOT / "web" / "static" / "js" / "app.js").read_text(encoding="utf-8")
CSS = (ROOT / "web" / "static" / "css" / "app.css").read_text(encoding="utf-8")


def test_top_apps_pulse_markup():
    assert 'id="topAppsPulse"' in HTML
    assert "Топ активностей" in HTML
    assert "Что делали" in HTML
    assert "pulse-apps-panel" in HTML
    assert 'id="activityDetailModal"' in HTML
    assert 'id="activityDetailList"' in HTML


def test_top_apps_pulse_render_hooks():
    assert "function renderTopAppsPulse" in JS
    assert "function topFocusCandidates" in JS
    assert "function resolveActivityBreakdown" in JS
    assert "function openActivityDetail" in JS
    assert "function setBodyScrollLock" in JS
    assert "function wireTopAppsPulse" in JS
    assert "data-pulse-idx" in JS
    assert "by_app_grouped" in JS
    assert "renderTopAppsPulse(summary)" in JS


def test_activity_modal_scroll_lock():
    assert "is-scroll-locked" in CSS
    assert "setBodyScrollLock(true)" in JS
    assert "setBodyScrollLock(false)" in JS
    assert "overscroll-behavior: contain" in CSS


def test_top_focus_prefers_nested_activities():
    assert "msedge.exe" in JS
    assert "mstsc.exe" in JS
    assert "formatActivityDisplayName" in JS
    assert "shortViaLabel" in JS
    assert "apps-podium-via" in CSS
    assert "apps-runner-via" in CSS


def test_top_apps_podium_styles():
    assert ".apps-podium" in CSS
    assert ".apps-cup-gold" in CSS
    assert ".apps-cup-halo" in CSS
    assert ".apps-cup-gem" in CSS
    assert ".apps-runners" in CSS
    assert 'html[data-theme="dark"] .apps-podium-card' in CSS
    assert ".activity-detail-row" in CSS
    assert ".apps-podium-icon .rank-icon" in CSS
    assert "object-fit: contain" in CSS
