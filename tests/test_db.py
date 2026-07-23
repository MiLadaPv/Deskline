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
    assert cfg["screenshots_enabled"] is False
    assert cfg["screenshot_retention_days"] == 7
    assert cfg["idle_after_sec"] == 180.0
    cfg["paused"] = True
    saved = save_config(cfg)
    assert saved["paused"] is True

    db = Database(data / "deskline.db")
    assert db.path.exists()
    assert db.summary_for_day()["total_sec"] == 0


def test_purge_old_screenshots(tmp_path: Path, monkeypatch):
    shots = tmp_path / "screenshots"
    monkeypatch.setattr("deskline.config.SCREENSHOTS_DIR", shots)
    monkeypatch.setattr("deskline.config.DATA_ROOT", tmp_path)
    monkeypatch.setattr("deskline.config.CONFIG_PATH", tmp_path / "config.json")
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


def test_custom_screenshots_dir_and_interval_persist(tmp_path: Path, monkeypatch):
    data = tmp_path / "Deskline"
    custom = tmp_path / "OtherDisk" / "shots"
    monkeypatch.setattr("deskline.config.DATA_ROOT", data)
    monkeypatch.setattr("deskline.config.DB_PATH", data / "deskline.db")
    monkeypatch.setattr("deskline.config.SCREENSHOTS_DIR", data / "screenshots")
    monkeypatch.setattr("deskline.config.CONFIG_PATH", data / "config.json")

    cfg = load_config()
    cfg["screenshot_interval_sec"] = 60
    cfg["screenshots_dir"] = str(custom)
    saved = save_config(cfg)
    assert saved["screenshot_interval_sec"] == 60
    assert saved["screenshots_dir"] == str(custom)
    assert custom.is_dir()

    from deskline.config import get_screenshots_dir

    assert get_screenshots_dir(saved) == custom
    again = load_config()
    assert again["screenshot_interval_sec"] == 60
    assert again["screenshots_dir"] == str(custom)


def test_pause_does_not_overwrite_screenshot_interval(tmp_path: Path, monkeypatch):
    data = tmp_path / "Deskline"
    monkeypatch.setattr("deskline.config.DATA_ROOT", data)
    monkeypatch.setattr("deskline.config.DB_PATH", data / "deskline.db")
    monkeypatch.setattr("deskline.config.SCREENSHOTS_DIR", data / "screenshots")
    monkeypatch.setattr("deskline.config.CONFIG_PATH", data / "config.json")
    monkeypatch.setattr("deskline.capture.SCREENSHOTS_DIR", data / "screenshots")

    cfg = load_config()
    cfg["screenshot_interval_sec"] = 60
    save_config(cfg)

    from deskline.tracker import Tracker

    tracker = Tracker(Database(data / "deskline.db"))
    tracker.cfg["screenshot_interval_sec"] = 300  # stale memory
    tracker.pause()
    assert load_config()["screenshot_interval_sec"] == 60
    assert tracker.cfg["screenshot_interval_sec"] == 60
    assert tracker.cfg["paused"] is True
