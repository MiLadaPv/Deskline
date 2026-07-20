from __future__ import annotations

import re
from pathlib import Path

from PIL import Image, ImageDraw

from deskline.config import ICONS_DIR, ensure_data_dirs

_SAFE_NAME = re.compile(r"[^a-zA-Z0-9._-]+")


def icon_cache_name(app_name: str) -> str:
    base = (app_name or "unknown.exe").strip().lower()
    safe = _SAFE_NAME.sub("_", base)
    if not safe.endswith(".png"):
        safe = f"{safe}.png"
    return safe


def icon_url_for_app(app_name: str | None) -> str:
    name = icon_cache_name(app_name or "unknown.exe")
    return f"/media/icons/{name}"


def icon_path_for_app(app_name: str | None) -> Path:
    ensure_data_dirs()
    return ICONS_DIR / icon_cache_name(app_name or "unknown.exe")


def ensure_app_icon(app_name: str | None, app_path: str | None = None) -> Path:
    """Extract and cache a 32x32 PNG icon for the given app. Returns cache path."""
    ensure_data_dirs()
    out = icon_path_for_app(app_name)
    if out.exists() and out.stat().st_size > 0:
        return out

    src = Path(app_path) if app_path else None
    if src and src.is_file():
        if _extract_exe_icon(src, out):
            return out

    _write_placeholder(out)
    return out


def _extract_exe_icon(exe_path: Path, out: Path) -> bool:
    try:
        import win32con
        import win32gui
        import win32ui
    except ImportError:
        return False

    large: list = []
    small: list = []
    try:
        large, small = win32gui.ExtractIconEx(str(exe_path), 0)
        handles = large or small
        if not handles:
            return False
        hicon = handles[0]
        size = 32
        hdc = win32ui.CreateDCFromHandle(win32gui.GetDC(0))
        hbmp = win32ui.CreateBitmap()
        hbmp.CreateCompatibleBitmap(hdc, size, size)
        hdc_mem = hdc.CreateCompatibleDC()
        hdc_mem.SelectObject(hbmp)
        try:
            hdc_mem.DrawIconEx(
                (0, 0),
                hicon,
                size,
                size,
                0,
                None,
                win32con.DI_NORMAL,
            )
        except Exception:
            hdc_mem.DrawIcon((0, 0), hicon)
        bmp_info = hbmp.GetInfo()
        bmp_str = hbmp.GetBitmapBits(True)
        img = Image.frombuffer(
            "RGBA",
            (bmp_info["bmWidth"], bmp_info["bmHeight"]),
            bmp_str,
            "raw",
            "BGRA",
            0,
            1,
        )
        img = img.resize((size, size), Image.Resampling.LANCZOS)
        img.save(out, format="PNG")
        return out.exists() and out.stat().st_size > 0
    except Exception:
        return False
    finally:
        for h in large:
            try:
                win32gui.DestroyIcon(h)
            except Exception:
                pass
        for h in small:
            try:
                win32gui.DestroyIcon(h)
            except Exception:
                pass


def _write_placeholder(out: Path) -> None:
    img = Image.new("RGBA", (32, 32), (215, 235, 227, 255))
    draw = ImageDraw.Draw(img)
    draw.ellipse((8, 8, 24, 24), fill=(47, 111, 94, 255))
    img.save(out, format="PNG")
