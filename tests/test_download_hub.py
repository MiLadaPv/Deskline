from __future__ import annotations

from pathlib import Path

from deskline.config import WEB_ROOT, brand_template_context


def test_download_hub_template_and_assets():
    html = (WEB_ROOT / "templates" / "download.html").read_text(encoding="utf-8")
    assert 'data-os="windows"' in html
    assert 'data-os="chromeos"' in html
    assert "dl-acc" in html
    assert "silent_install.bat" in html or "silent_install_bat_url" in html
    assert "Chrome-расширение" in html or "Chrome" in html
    assert "Mobile" in html
    assert "download_click" in html
    assert (WEB_ROOT / "static" / "install" / "silent_install.bat").is_file()
    assert (WEB_ROOT / "static" / "install" / "silent_install.ps1").is_file()


def test_brand_context_has_download_hub_fields():
    ctx = brand_template_context(version="9.9.9")
    assert ctx["silent_install_bat_url"] == "/static/install/silent_install.bat"
    assert ctx["silent_install_ps1_url"] == "/static/install/silent_install.ps1"
    assert "chrome_web_store_url" in ctx
    assert ctx["download_extension_url"].endswith("/releases/latest")


def test_welcome_points_to_download_hub():
    welcome = (WEB_ROOT / "templates" / "welcome.html").read_text(encoding="utf-8")
    assert 'href="/download"' in welcome
    compare = (WEB_ROOT / "templates" / "compare.html").read_text(encoding="utf-8")
    assert 'href="/download"' in compare
