from __future__ import annotations

from deskline.main import _uvicorn_log_config


def test_uvicorn_log_config_has_plain_formatters():
    cfg = _uvicorn_log_config()
    assert "formatters" in cfg
    assert "()" not in cfg["formatters"]["default"]
    assert "uvicorn.logging" not in str(cfg)
