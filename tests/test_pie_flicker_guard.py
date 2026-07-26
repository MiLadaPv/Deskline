"""Guard against pie-chart flicker regressions (entrance animation on every poll)."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CSS = (ROOT / "web" / "static" / "css" / "app.css").read_text(encoding="utf-8")
JS = (ROOT / "web" / "static" / "js" / "app.js").read_text(encoding="utf-8")


def test_donut_pop_only_on_enter_class():
    # Unconditional animation on .donut-seg restarts every poll → flicker.
    assert "animation: donutPop" in CSS
    assert ".donut-segs.is-enter .donut-seg" in CSS
    # Base segment rule must not include donutPop (only the is-enter rule).
    base = CSS.split(".donut-seg {", 1)[1].split("}", 1)[0]
    assert "donutPop" not in base


def test_pie_chart_skips_identical_signature():
    assert "function pieSignature(" in JS
    assert "el.dataset.pieSig === sig" in JS
    assert "lastDayViewKey" in JS
    assert "donut-segs${enterClass}" in JS or 'donut-segs${enterClass}' in JS
