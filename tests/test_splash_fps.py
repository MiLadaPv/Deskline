"""Boot splash must stay GPU-friendly: flush stencil mark + letter wave loader."""

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


def test_boot_bars_are_flush_stencil_under_d():
    assert "clipPath" in BOOT
    assert 'clip-path="url(' in BOOT
    assert "logo-bars" in BOOT
    assert BOOT.find('class="logo-bars"') < BOOT.find('class="logo-d"')
    assert "BAR_BOTTOM = 612" in BUILDER
    assert "(248," in BUILDER  # flush to hole left edge
    assert 'x="248"' in BOOT
    assert 'height="148"' in BOOT or 'height="236"' in BOOT
    # Bottom of bars reaches past hole floor so clip sits on the letter edge
    assert "612" in BUILDER


def test_boot_css_preserves_gradients_and_enlarges_mark():
    boot_idx = CSS.find(".boot-splash {")
    assert boot_idx >= 0
    chunk = CSS[boot_idx : boot_idx + 4500]
    assert "bootBarGrow" in chunk
    assert "bootLetterIn" in chunk
    assert "min(240px, 56vw)" in chunk
    assert "clamp(1.85rem" in chunk
    assert ".logo-mark .logo-bar-1" in CSS
    assert ".boot-logo-svg .logo-bar-1" in CSS
    assert "revert-layer" in CSS
    # Must not be a bare global solid fill rule
    assert "\n.logo-bar-1 { fill:" not in CSS
    assert CSS.count(".logo-bar-1 { fill: #3b82f6; }") == 0


def test_boot_letter_loader_replaces_progress_line():
    assert "boot-letter" in INDEX
    assert "boot-letter" in LOGIN
    assert "boot-progress" not in INDEX
    assert "boot-progress" not in LOGIN
    assert 'aria-label="Deskline"' in INDEX


def test_boot_js_plays_and_exits_cleanly():
    assert 'classList.add("is-playing")' in JS
    assert 'classList.add("is-leaving")' in JS
    assert "prefers-reduced-motion" in JS
    assert "deskline_splash_done" in JS
