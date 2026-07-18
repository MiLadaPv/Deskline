from __future__ import annotations

import threading
from typing import Callable

from PIL import Image, ImageDraw


def _make_icon(recording: bool) -> Image.Image:
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    # Paper disc
    draw.ellipse((4, 4, 60, 60), fill=(245, 236, 220, 255), outline=(34, 48, 42, 255), width=3)
    if recording:
        draw.ellipse((22, 22, 42, 42), fill=(196, 74, 58, 255))
    else:
        draw.rectangle((22, 22, 42, 42), fill=(90, 110, 100, 255))
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
        return "Deskline · Recording" if not st.get("paused") else "Deskline · Paused"

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

    def run() -> None:
        icon.run()

    t = threading.Thread(target=run, name="deskline-tray", daemon=True)
    t.start()
    return t
