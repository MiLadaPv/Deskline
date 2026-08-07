from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
JS = (ROOT / "web" / "static" / "js" / "app.js").read_text(encoding="utf-8")
CSS = (ROOT / "web" / "static" / "css" / "app.css").read_text(encoding="utf-8")


def test_ctrl_wheel_zoom_hooks():
    assert "function wireZoomControls" in JS
    assert "wireZoomControls()" in JS
    assert "UI_TEXT_SCALE_KEY" in JS
    assert "CHART_SCALE_KEY" in JS
    assert "findChartZoomHost" in JS
    assert "--ui-text-scale" in CSS
    assert "--chart-scale" in CSS
    assert "calc(100% * var(--ui-text-scale))" in CSS
