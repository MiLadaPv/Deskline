from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CSS = (ROOT / "web" / "static" / "css" / "app.css").read_text(encoding="utf-8")
JS = (ROOT / "web" / "static" / "js" / "app.js").read_text(encoding="utf-8")


def test_2026_motion_contracts():
    assert "@keyframes shellRise" in CSS
    assert "@keyframes panelStage" in CSS
    assert "@keyframes metricTick" in CSS
    assert "@keyframes preview-bar-rise" in CSS
    assert "animation: donutPop" in CSS
    assert ".donut-segs.is-enter .donut-seg" in CSS
    assert "is-shell-ready" in CSS
    assert "prefers-reduced-motion" in CSS


def test_shell_ready_and_metric_pulse_hooks():
    assert 'classList.add("is-shell-ready")' in JS
    assert "function pulseMetric" in JS
    assert 'classList.add("is-tick")' in JS
    assert '"meetings"' in JS
