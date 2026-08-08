"""Boot splash must stay GPU-friendly: stencil vector mark + letter wave loader."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CSS = (ROOT / "web" / "static" / "css" / "app.css").read_text(encoding="utf-8")
BOOT = (ROOT / "web" / "templates" / "partials" / "boot_logo.html").read_text(encoding="utf-8")
JS = (ROOT / "web" / "static" / "js" / "app.js").read_text(encoding="utf-8")
INDEX = (ROOT / "web" / "templates" / "index.html").read_text(encoding="utf-8")
LOGIN = (ROOT / "web" / "templates" / "login.html").read_text(encoding="utf-8")
BUILDER = (ROOT / "scripts" / "rebuild_logo_vector.py").read_text(encoding="utf-8")


def test_boot_logo_is_inline_vector_not_webp_movie():
    assert "boot-logo-svg" in BOOT
    assert "logo-bar-scale" in BOOT
    assert "logo-grow.webp" not in BOOT
    assert "logo-grow-dark.webp" not in BOOT
    assert "<svg" in BOOT


def test_boot_bars_are_stencil_clipped_under_d():
    assert "clipPath" in BOOT
    assert 'clip-path="url(' in BOOT
    assert "logo-bars" in BOOT
    # Bars group must appear before the D path (D paints on top).
    assert BOOT.find('class="logo-bars"') < BOOT.find('class="logo-d"')
    assert "D_HOLE" in BUILDER or "clipPath" in BUILDER
    assert "(270," in BUILDER  # bars inset past hole edge ~248


def test_boot_css_uses_compositor_props_only():
    boot_idx = CSS.find(".boot-splash {")
    assert boot_idx >= 0
    chunk = CSS[boot_idx : boot_idx + 4500]
    assert "bootBarGrow" in chunk
    assert "bootMarkIn" in chunk
    assert "bootLetterIn" in chunk
    assert "bootLetterPulse" in chunk
    assert "boot-progress" not in chunk
    assert "filter: blur" not in chunk
    assert "boot-glow" not in chunk
    shell = CSS[CSS.find("@keyframes shellRise") : CSS.find("@keyframes shellRise") + 220]
    assert "filter: blur" not in shell


def test_boot_letter_loader_replaces_progress_line():
    assert "boot-letter" in INDEX
    assert "boot-letter" in LOGIN
    assert "boot-progress" not in INDEX
    assert "boot-progress" not in LOGIN
    assert 'aria-label="Deskline"' in INDEX
    assert CSS.count("boot-letter") >= 2


def test_boot_js_plays_and_exits_cleanly():
    assert 'classList.add("is-playing")' in JS
    assert 'classList.add("is-leaving")' in JS
    assert "prefers-reduced-motion" in JS
    assert "deskline_splash_done" in JS
