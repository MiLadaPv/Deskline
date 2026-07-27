from __future__ import annotations

from pathlib import Path

import pytest

from deskline.db import Database, ProjectNameExists
from deskline.mini_tracker import _fmt_elapsed


def test_create_project_rejects_duplicate_name(tmp_path: Path) -> None:
    db = Database(tmp_path / "p.db")
    db.create_project("RG-Soft", "#2f6f5e")
    with pytest.raises(ProjectNameExists):
        db.create_project("rg-soft", "#111111")
    with pytest.raises(ProjectNameExists):
        db.create_project("  RG-Soft  ", "#222222")


def test_rename_project_rejects_duplicate(tmp_path: Path) -> None:
    db = Database(tmp_path / "p.db")
    a = db.create_project("Alpha", "#2f6f5e")
    b = db.create_project("Beta", "#2f6f5e")
    with pytest.raises(ProjectNameExists):
        db.update_project(b["id"], name="alpha")
    updated = db.update_project(a["id"], name="Alpha One")
    assert updated["name"] == "Alpha One"


def test_fmt_elapsed() -> None:
    assert _fmt_elapsed(65) == "1:05"
    assert _fmt_elapsed(3661) == "1:01:01"


def test_orient_for_position_flips_at_right_edge() -> None:
    from deskline.mini_tracker import _orient_for_position

    assert _orient_for_position(100, 272, 1280) == "horizontal"
    assert _orient_for_position(1280 - 272 - 5, 272, 1280) == "vertical"
    assert _orient_for_position(1280 - 60 - 8, 60, 1280) == "vertical"


def test_focus_label_prefers_project() -> None:
    from deskline.mini_tracker import _focus_label

    snap = {"project_name": "RG-Soft", "task_name": "КРАСНЫЙ ЛУЧ RLS"}
    assert "RG-Soft" in _focus_label(snap, vertical=False)
    assert _focus_label(snap, vertical=True) == "RG-Soft"
