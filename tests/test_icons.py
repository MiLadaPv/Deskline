from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from PIL import Image

from deskline.icons import (
    _APP_ICON_REV,
    _ICON_SIZE,
    _trim_and_fit,
    ensure_app_icon,
    ensure_site_icon,
    icon_cache_name,
    icon_cache_name_for_site,
    icon_path_for_app,
    icon_url_for_app,
    icon_url_for_site,
    is_site_icon_name,
    is_weak_icon_cache,
    purge_placeholder_icons,
    shared_placeholder_path,
    site_from_icon_name,
)


def test_icon_cache_name_and_url():
    assert icon_cache_name("MSEdge.EXE") == f"msedge.exe.{_APP_ICON_REV}.png"
    url = icon_url_for_app("msedge.exe")
    assert url.startswith(f"/media/icons/msedge.exe.{_APP_ICON_REV}.png?v=")


def test_app_name_from_icon_filename():
    from deskline.icons import app_name_from_icon_filename

    assert app_name_from_icon_filename(f"msedge.exe.{_APP_ICON_REV}.png") == "msedge.exe"
    assert app_name_from_icon_filename("msedge.exe.v2.png") == "msedge.exe"
    assert app_name_from_icon_filename("site_habr.com.v3.png") is None
    assert app_name_from_icon_filename("placeholder.png") is None


def test_ensure_app_icon_uses_shared_placeholder(tmp_path: Path, monkeypatch):
    icons = tmp_path / "icons"
    monkeypatch.setattr("deskline.icons.ICONS_DIR", icons)
    monkeypatch.setattr("deskline.config.ICONS_DIR", icons)

    out = ensure_app_icon("fakeapp.exe", app_path=None)
    assert out.name == "placeholder.png"
    assert out.exists()
    assert not (icons / "fakeapp.exe.png").exists()
    img = Image.open(out)
    assert img.size == (_ICON_SIZE, _ICON_SIZE)


def test_weak_placeholder_does_not_block_real_extract(tmp_path: Path, monkeypatch):
    icons = tmp_path / "icons"
    icons.mkdir()
    monkeypatch.setattr("deskline.icons.ICONS_DIR", icons)
    monkeypatch.setattr("deskline.config.ICONS_DIR", icons)

    # Legacy placeholder size band (~200 bytes)
    weak = icons / f"msedge.exe.{_APP_ICON_REV}.png"
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

    weak = icons / "cursor.exe.v2.png"
    Image.new("RGBA", (32, 32), (215, 235, 227, 255)).save(weak, format="PNG")
    # Also leave a legacy pre-v2 name that purge should remove
    legacy = icons / "cursor.exe.png"
    Image.new("RGBA", (32, 32), (10, 10, 10, 255)).save(legacy, format="PNG")
    shared_placeholder_path()
    assert purge_placeholder_icons() >= 1
    assert not weak.exists()
    assert not legacy.exists()
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
    assert path == icons / f"chrome.exe.{_APP_ICON_REV}.png"


def test_site_icon_names_and_urls():
    assert icon_cache_name_for_site("Habr.com") == f"site_habr.com.{_APP_ICON_REV}.png"
    assert icon_url_for_site("habr.com").startswith(
        f"/media/icons/site_habr.com.{_APP_ICON_REV}.png?v="
    )
    assert is_site_icon_name(f"site_habr.com.{_APP_ICON_REV}.png")
    assert not is_site_icon_name(f"msedge.exe.{_APP_ICON_REV}.png")
    assert site_from_icon_name(f"site_habr.com.{_APP_ICON_REV}.png") == "habr.com"
    assert site_from_icon_name("site_messenger.yandex.ru.png") == "messenger.yandex.ru"


def test_trim_and_fit_fills_canvas():
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    # Small opaque square in the center with lots of transparent padding
    for x in range(24, 40):
        for y in range(24, 40):
            img.putpixel((x, y), (255, 0, 0, 255))
    out = _trim_and_fit(img, size=32, padding=2)
    assert out.size == (32, 32)
    # Content should occupy most of the inner area (not stay tiny in the center)
    bbox = out.getbbox()
    assert bbox is not None
    bw = bbox[2] - bbox[0]
    bh = bbox[3] - bbox[1]
    assert bw >= 24
    assert bh >= 24


def test_trim_and_fit_app_padding_keeps_margin():
    """Edge-like circular logo must not touch the canvas edge."""
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    for x in range(64):
        for y in range(64):
            dx, dy = x - 31.5, y - 31.5
            if dx * dx + dy * dy <= 30 * 30:
                img.putpixel((x, y), (0, 120, 215, 255))
    out = _trim_and_fit(img, size=32, padding=5, max_fill=0.88)
    bbox = out.getbbox()
    assert bbox is not None
    assert bbox[0] >= 2
    assert bbox[1] >= 2
    assert bbox[2] <= 30
    assert bbox[3] <= 30


def test_bytes_to_icon_rejects_blank_transparent(tmp_path: Path, monkeypatch):
    from deskline.icons import _bytes_to_icon_png

    icons = tmp_path / "icons"
    icons.mkdir()
    monkeypatch.setattr("deskline.icons.ICONS_DIR", icons)
    blank = Image.new("RGBA", (1, 1), (0, 0, 0, 0))
    buf = __import__("io").BytesIO()
    blank.save(buf, format="PNG")
    out = icons / "site_blank.png"
    assert _bytes_to_icon_png(buf.getvalue(), out) is False
    assert not out.exists()


def test_weak_site_cache_detects_blank(tmp_path: Path, monkeypatch):
    icons = tmp_path / "icons"
    icons.mkdir()
    monkeypatch.setattr("deskline.icons.ICONS_DIR", icons)
    monkeypatch.setattr("deskline.config.ICONS_DIR", icons)
    blank = icons / f"site_messenger.yandex.ru.{_APP_ICON_REV}.png"
    Image.new("RGBA", (32, 32), (0, 0, 0, 0)).save(blank, format="PNG")
    assert is_weak_icon_cache(blank)


def test_resolve_icon_url_prefers_site(tmp_path: Path, monkeypatch):
    from deskline.icons import resolve_icon_url

    icons = tmp_path / "icons"
    icons.mkdir()
    monkeypatch.setattr("deskline.icons.ICONS_DIR", icons)
    monkeypatch.setattr("deskline.config.ICONS_DIR", icons)

    url = resolve_icon_url(site="messenger.yandex.ru", app_name="msedge.exe")
    assert url.startswith(f"/media/icons/site_messenger.yandex.ru.{_APP_ICON_REV}.png?v=")


def test_resolve_icon_url_falls_back_to_app(tmp_path: Path, monkeypatch):
    from deskline.icons import resolve_icon_url

    icons = tmp_path / "icons"
    icons.mkdir()
    monkeypatch.setattr("deskline.icons.ICONS_DIR", icons)
    monkeypatch.setattr("deskline.config.ICONS_DIR", icons)

    url = resolve_icon_url(site=None, app_name="msedge.exe")
    assert url.startswith(f"/media/icons/msedge.exe.{_APP_ICON_REV}.png?v=")


def test_restore_alpha_if_needed():
    from deskline.icons import _restore_alpha_if_needed

    # BGRA-like content with alpha=0 everywhere (GDI quirk)
    img = Image.new("RGBA", (8, 8), (0, 0, 0, 0))
    for x in range(2, 6):
        for y in range(2, 6):
            img.putpixel((x, y), (0, 120, 215, 0))
    fixed = _restore_alpha_if_needed(img)
    assert fixed.getpixel((3, 3))[3] == 255
    assert fixed.getpixel((0, 0))[3] == 0


def test_ensure_site_icon_caches_favicon(tmp_path: Path, monkeypatch):
    icons = tmp_path / "icons"
    monkeypatch.setattr("deskline.icons.ICONS_DIR", icons)
    monkeypatch.setattr("deskline.config.ICONS_DIR", icons)

    fav = Image.new("RGBA", (64, 64), (10, 120, 200, 255))
    buf = __import__("io").BytesIO()
    fav.save(buf, format="PNG")
    payload = buf.getvalue()

    class _Resp:
        def read(self):
            return payload

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    with patch("deskline.icons.urllib.request.urlopen", return_value=_Resp()):
        out = ensure_site_icon("habr.com")

    assert out.name == f"site_habr.com.{_APP_ICON_REV}.png"
    assert out.exists()
    assert not is_weak_icon_cache(out)
    img = Image.open(out)
    assert img.size == (_ICON_SIZE, _ICON_SIZE)


def test_resolve_exe_path_via_registry_uninstall(tmp_path: Path, monkeypatch):
    from deskline.icons import resolve_exe_path

    fake_exe = tmp_path / "KeePass.exe"
    fake_exe.write_bytes(b"MZ")

    def fake_registry(name: str):
        assert name.lower() == "keepass.exe"
        return fake_exe

    monkeypatch.setattr("deskline.icons._resolve_via_registry", fake_registry)
    monkeypatch.setattr("deskline.icons.shutil.which", lambda n: None)
    found = resolve_exe_path("keepass.exe", None)
    assert found == fake_exe


def test_resolve_exe_path_accepts_displayicon_suffix(tmp_path: Path):
    from deskline.icons import resolve_exe_path

    fake_exe = tmp_path / "app.exe"
    fake_exe.write_bytes(b"MZ")
    found = resolve_exe_path("app.exe", f"{fake_exe},0")
    assert found == fake_exe
