from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / "web" / "templates" / "index.html").read_text(encoding="utf-8")
CSS = (ROOT / "web" / "static" / "css" / "app.css").read_text(encoding="utf-8")


def test_shots_toolbar_modern_shell():
    assert 'id="panel-shots"' in HTML
    assert 'class="shots-toolbar"' in HTML
    assert 'id="shotsDay"' in HTML
    assert 'id="shotsAppFilter"' in HTML
    assert 'id="shotsShowDetails"' in HTML
    assert 'id="refreshShotsBtn"' in HTML
    assert 'id="shotsFilterMeta"' in HTML
    assert ".shots-toolbar" in CSS
    assert ".shots-chip" in CSS
    assert ".shots-refresh" in CSS
