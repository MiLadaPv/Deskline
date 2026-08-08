"""Boot splash must stay GPU-friendly: vector mark + compositor transforms only."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CSS = (ROOT / "web" / "static" / "css" / "app.css").read_text(encoding="utf-8")
BOOT = (ROOT / "web" / "templates" / "partials" / "boot_logo.html").read_text(encoding="utf-8")
JS = (ROOT / "web" / "static" / "js" / "app.js").read_text(encoding="utf-8")


def test_boot_logo_is_inline_vector_not_webp_movie():
    assert "boot-logo-svg" in BOOT
    assert "logo-bar-scale" in BOOT
    assert "logo-grow.webp" not in BOOT
    assert "logo-grow-dark.webp" not in BOOT
    assert "<svg" in BOOT


def test_boot_css_uses_compositor_props_only():
    boot_idx = CSS.find(".boot-splash {")
    assert boot_idx >= 0
    chunk = CSS[boot_idx : boot_idx + 4500]
    assert "bootBarGrow" in chunk
    assert "bootMarkIn" in chunk
    assert "bootTitleIn" in chunk
    assert "bootProgressDraw" in chunk
    assert "letter-spacing" not in chunk.split("@keyframes bootTitleIn")[1].split("}")[0]
    assert "filter: blur" not in chunk
    assert "boot-glow" not in chunk
    assert "will-change: transform, opacity" in chunk or "translate3d" in chunk
    assert "filter: blur" not in CSS[CSS.find("@keyframes shellRise") : CSS.find("@keyframes shellRise") + 220]


def test_boot_js_plays_and_exits_cleanly():
    assert 'classList.add("is-playing")' in JS
    assert 'classList.add("is-leaving")' in JS
    assert "prefers-reduced-motion" in JS
    assert "deskline_splash_done" in JS
