from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

from deskline.config import ensure_data_dirs, load_config, save_config
from deskline.db import Database


def test_smoke_init(tmp_path: Path, monkeypatch):
    data = tmp_path / "Deskline"
    monkeypatch.setattr("deskline.config.DATA_ROOT", data)
    monkeypatch.setattr("deskline.config.DB_PATH", data / "deskline.db")
    monkeypatch.setattr("deskline.config.SCREENSHOTS_DIR", data / "screenshots")
    monkeypatch.setattr("deskline.config.CONFIG_PATH", data / "config.json")

    ensure_data_dirs()
    assert (data / "screenshots").is_dir()

    cfg = load_config()
    assert cfg["screenshots_enabled"] is True
    assert cfg["screenshot_retention_days"] == 7
    cfg["paused"] = True
    saved = save_config(cfg)
    assert saved["paused"] is True

    db = Database(data / "deskline.db")
    assert db.path.exists()
    assert db.summary_for_day()["total_sec"] == 0


def test_purge_old_screenshots(tmp_path: Path, monkeypatch):
    shots = tmp_path / "screenshots"
    monkeypatch.setattr("deskline.config.SCREENSHOTS_DIR", shots)
    monkeypatch.setattr("deskline.db.SCREENSHOTS_DIR", shots)
    ensure_data_dirs()

    db = Database(tmp_path / "deskline.db")
    old_file = shots / "old.jpg"
    new_file = shots / "new.jpg"
    old_file.write_bytes(b"old")
    new_file.write_bytes(b"new")

    old_at = datetime.now().astimezone() - timedelta(days=10)
    new_at = datetime.now().astimezone()
    db.add_screenshot(str(old_file), reason="interval", session_id=None, taken_at=old_at)
    db.add_screenshot(str(new_file), reason="interval", session_id=None, taken_at=new_at)

    result = db.purge_old_screenshots(7)
    assert result["deleted_rows"] == 1
    assert not old_file.exists()
    assert new_file.exists()
    assert len(db.screenshots_for_date()) == 1
