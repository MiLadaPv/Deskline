from __future__ import annotations

import threading
from pathlib import Path
from typing import Callable

from PIL import Image, ImageDraw

from deskline.config import PROJECT_ROOT
from deskline.notify import set_tray_icon


def _brand_base() -> Image.Image:
    candidates = [
        PROJECT_ROOT / "assets" / "tray.png",
        PROJECT_ROOT / "assets" / "deskline-icon.png",
        Path(__file__).resolve().parent.parent / "assets" / "tray.png",
        Path(__file__).resolve().parent.parent / "assets" / "deskline-icon.png",
    ]
    for path in candidates:
        if path.exists():
            img = Image.open(path).convert("RGBA")
            return img.resize((64, 64), Image.Resampling.LANCZOS)

    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle((2, 2, 61, 61), radius=14, fill=(243, 235, 224, 255))
    draw.line((20, 14, 20, 50), fill=(31, 42, 36, 220), width=3)
    draw.rounded_rectangle((26, 16, 48, 22), radius=3, fill=(47, 111, 94, 255))
    draw.rounded_rectangle((26, 28, 42, 34), radius=3, fill=(47, 111, 94, 220))
    draw.rounded_rectangle((26, 40, 36, 46), radius=3, fill=(47, 111, 94, 180))
    return img


def _make_icon(recording: bool) -> Image.Image:
    img = _brand_base().copy()
    draw = ImageDraw.Draw(img)
    if recording:
        draw.ellipse((42, 42, 58, 58), fill=(196, 90, 58, 255), outline=(243, 235, 224, 255), width=2)
    else:
        draw.rounded_rectangle((44, 44, 56, 56), radius=2, fill=(90, 110, 100, 255), outline=(243, 235, 224, 255), width=2)
    return img


def start_tray(
    get_status: Callable[[], dict],
    on_pause: Callable[[], None],
    on_resume: Callable[[], None],
    on_open: Callable[[], None],
    on_quit: Callable[[], None],
) -> threading.Thread:
    import pystray
    from pystray import MenuItem as Item

    icon_img = _make_icon(True)

    def title() -> str:
        st = get_status()
        if st.get("paused"):
            return "Deskline · Paused"
        if st.get("idle"):
            return "Deskline · Idle"
        return "Deskline · Recording"

    def refresh(icon: "pystray.Icon") -> None:
        st = get_status()
        icon.icon = _make_icon(not st.get("paused"))
        icon.title = title()

    def pause(icon: "pystray.Icon", _item: object) -> None:
        on_pause()
        refresh(icon)

    def resume(icon: "pystray.Icon", _item: object) -> None:
        on_resume()
        refresh(icon)

    def open_dash(icon: "pystray.Icon", _item: object) -> None:
        on_open()

    def quit_app(icon: "pystray.Icon", _item: object) -> None:
        set_tray_icon(None)
        icon.stop()
        on_quit()

    menu = pystray.Menu(
        Item(lambda item: title(), None, enabled=False),
        Item("Open dashboard", open_dash),
        Item("Pause", pause),
        Item("Resume", resume),
        Item("Quit", quit_app),
    )
    icon = pystray.Icon("Deskline", icon_img, title(), menu)
    set_tray_icon(icon)

    def run() -> None:
        icon.run()

    t = threading.Thread(target=run, name="deskline-tray", daemon=True)
    t.start()
    return t
