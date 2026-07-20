from __future__ import annotations

from pathlib import Path

from PIL import Image

from deskline.icons import (
    ensure_app_icon,
    icon_cache_name,
    icon_path_for_app,
    icon_url_for_app,
)


def test_icon_cache_name_and_url():
    assert icon_cache_name("MSEdge.EXE") == "msedge.exe.png"
    assert icon_url_for_app("msedge.exe") == "/media/icons/msedge.exe.png"


def test_ensure_app_icon_writes_placeholder(tmp_path: Path, monkeypatch):
    icons = tmp_path / "icons"
    monkeypatch.setattr("deskline.icons.ICONS_DIR", icons)
    monkeypatch.setattr("deskline.config.ICONS_DIR", icons)

    out = ensure_app_icon("fakeapp.exe", app_path=None)
    assert out.exists()
    assert out.name == "fakeapp.exe.png"
    img = Image.open(out)
    assert img.size == (32, 32)
    assert img.format == "PNG"


def test_ensure_app_icon_uses_cache(tmp_path: Path, monkeypatch):
    icons = tmp_path / "icons"
    monkeypatch.setattr("deskline.icons.ICONS_DIR", icons)
    monkeypatch.setattr("deskline.config.ICONS_DIR", icons)

    first = ensure_app_icon("cached.exe")
    mtime = first.stat().st_mtime
    second = ensure_app_icon("cached.exe")
    assert second == first
    assert second.stat().st_mtime == mtime


def test_icon_path_for_app(tmp_path: Path, monkeypatch):
    icons = tmp_path / "icons"
    monkeypatch.setattr("deskline.icons.ICONS_DIR", icons)
    monkeypatch.setattr("deskline.config.ICONS_DIR", icons)
    path = icon_path_for_app("chrome.exe")
    assert path == icons / "chrome.exe.png"
