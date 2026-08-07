from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
JS = (ROOT / "web" / "static" / "js" / "app.js").read_text(encoding="utf-8")
HTML = (ROOT / "web" / "templates" / "index.html").read_text(encoding="utf-8")


def test_usage_pie_center_shows_total_not_focus_only():
    assert 'data-center-mode="total"' in JS
    assert "<span>всего</span>" in JS
    assert "usageTotalLine" in HTML
    assert "Всего ${fmtDur(total)}" in JS or "Всего ${fmtDur(total)}" in JS.replace(" ", "")
    assert "в фокусе ${fmtDur(focus)}" in JS
