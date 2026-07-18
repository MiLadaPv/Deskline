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
    cfg["paused"] = True
    saved = save_config(cfg)
    assert saved["paused"] is True

    db = Database(data / "deskline.db")
    assert db.path.exists()
    assert db.summary_for_day()["total_sec"] == 0
