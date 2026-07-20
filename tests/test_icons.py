from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from PIL import Image

from deskline.icons import (
    ensure_app_icon,
    icon_cache_name,
    icon_path_for_app,
    icon_url_for_app,
    is_weak_icon_cache,
    purge_placeholder_icons,
    shared_placeholder_path,
)


def test_icon_cache_name_and_url():
    assert icon_cache_name("MSEdge.EXE") == "msedge.exe.png"
    assert icon_url_for_app("msedge.exe") == "/media/icons/msedge.exe.png"


def test_ensure_app_icon_uses_shared_placeholder(tmp_path: Path, monkeypatch):
    icons = tmp_path / "icons"
    monkeypatch.setattr("deskline.icons.ICONS_DIR", icons)
    monkeypatch.setattr("deskline.config.ICONS_DIR", icons)

    out = ensure_app_icon("fakeapp.exe", app_path=None)
    assert out.name == "placeholder.png"
    assert out.exists()
    assert not (icons / "fakeapp.exe.png").exists()
    img = Image.open(out)
    assert img.size == (32, 32)


def test_weak_placeholder_does_not_block_real_extract(tmp_path: Path, monkeypatch):
    icons = tmp_path / "icons"
    icons.mkdir()
    monkeypatch.setattr("deskline.icons.ICONS_DIR", icons)
    monkeypatch.setattr("deskline.config.ICONS_DIR", icons)

    # Legacy placeholder size band (~200 bytes)
    weak = icons / "msedge.exe.png"
    Image.new("RGBA", (32, 32), (215, 235, 227, 255)).save(weak, format="PNG")
    assert is_weak_icon_cache(weak)

    fake_exe = tmp_path / "msedge.exe"
    fake_exe.write_bytes(b"MZ")

    def fake_extract(exe_path: Path, out: Path) -> bool:
        # Distinct from placeholder and outside the 150–220 weak band
        payload = b"\x89PNG\r\n\x1a\n" + (b"REALICON" * 80)
        out.write_bytes(payload)
        return True

    with patch("deskline.icons.resolve_exe_path", return_value=fake_exe):
        with patch("deskline.icons._extract_exe_icon", side_effect=fake_extract):
            out = ensure_app_icon("msedge.exe", str(fake_exe))

    assert out == weak
    assert out.exists()
    assert not is_weak_icon_cache(out)


def test_purge_placeholder_icons(tmp_path: Path, monkeypatch):
    icons = tmp_path / "icons"
    icons.mkdir()
    monkeypatch.setattr("deskline.icons.ICONS_DIR", icons)
    monkeypatch.setattr("deskline.config.ICONS_DIR", icons)

    weak = icons / "cursor.exe.png"
    Image.new("RGBA", (32, 32), (215, 235, 227, 255)).save(weak, format="PNG")
    shared_placeholder_path()
    assert purge_placeholder_icons() >= 1
    assert not weak.exists()
    assert (icons / "placeholder.png").exists()


def test_ensure_app_icon_caches_real_icon(tmp_path: Path, monkeypatch):
    icons = tmp_path / "icons"
    monkeypatch.setattr("deskline.icons.ICONS_DIR", icons)
    monkeypatch.setattr("deskline.config.ICONS_DIR", icons)

    fake_exe = tmp_path / "app.exe"
    fake_exe.write_bytes(b"MZ")

    def fake_extract(exe_path: Path, out: Path) -> bool:
        out.write_bytes(b"\x89PNG\r\n\x1a\n" + (b"CACHED" * 100))
        return True

    with patch("deskline.icons.resolve_exe_path", return_value=fake_exe):
        with patch("deskline.icons._extract_exe_icon", side_effect=fake_extract):
            first = ensure_app_icon("app.exe", str(fake_exe))
            mtime = first.stat().st_mtime_ns
            second = ensure_app_icon("app.exe", str(fake_exe))

    assert first == second
    assert second.stat().st_mtime_ns == mtime


def test_icon_path_for_app(tmp_path: Path, monkeypatch):
    icons = tmp_path / "icons"
    monkeypatch.setattr("deskline.icons.ICONS_DIR", icons)
    monkeypatch.setattr("deskline.config.ICONS_DIR", icons)
    path = icon_path_for_app("chrome.exe")
    assert path == icons / "chrome.exe.png"
