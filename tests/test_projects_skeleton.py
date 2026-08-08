from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
JS = (ROOT / "web" / "static" / "js" / "app.js").read_text(encoding="utf-8")
CSS = (ROOT / "web" / "static" / "css" / "app.css").read_text(encoding="utf-8")


def test_projects_skeleton_matches_pt_row():
    assert 'kind === "projects"' in JS
    assert "skel-pt-row" in JS
    assert "skel-pt-head" in JS
    assert "skel-pt-expand" in JS
    assert "skel-pt-task" in JS
    assert ".skel-pt-row" in CSS
    assert ".skel-pt-head" in CSS
    assert "grid-template-columns: 1rem 10px minmax(0, 1fr)" in CSS
