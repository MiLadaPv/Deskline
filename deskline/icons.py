from __future__ import annotations

import os
import re
import shutil
from pathlib import Path

from PIL import Image, ImageDraw

from deskline.config import ICONS_DIR, ensure_data_dirs

_SAFE_NAME = re.compile(r"[^a-zA-Z0-9._-]+")
# Placeholder PNGs from the old buggy cache are ~200 bytes; real icons are larger.
_WEAK_CACHE_MAX_BYTES = 400
_PLACEHOLDER_NAME = "placeholder.png"


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


def shared_placeholder_path() -> Path:
    ensure_data_dirs()
    out = ICONS_DIR / _PLACEHOLDER_NAME
    if not out.exists() or out.stat().st_size == 0:
        _write_placeholder(out)
    return out


def is_weak_icon_cache(path: Path) -> bool:
    """True if missing, empty, or a Deskline placeholder left by a failed extract."""
    if not path.exists() or not path.is_file():
        return True
    if path.name == _PLACEHOLDER_NAME:
        return False
    size = path.stat().st_size
    if size == 0:
        return True
    ph = ICONS_DIR / _PLACEHOLDER_NAME
    if ph.exists():
        try:
            if path.read_bytes() == ph.read_bytes():
                return True
        except OSError:
            pass
    # Legacy per-app placeholders were a solid teal circle (~110–220 bytes).
    if size <= 220:
        return True
    return False


def purge_placeholder_icons() -> int:
    """Remove per-app placeholder PNGs so real icons can be re-extracted."""
    ensure_data_dirs()
    removed = 0
    for path in ICONS_DIR.glob("*.png"):
        if path.name == _PLACEHOLDER_NAME:
            continue
        if is_weak_icon_cache(path):
            try:
                path.unlink()
                removed += 1
            except OSError:
                pass
    return removed


def resolve_exe_path(app_name: str | None, app_path: str | None = None) -> Path | None:
    if app_path:
        candidate = Path(app_path)
        if candidate.is_file():
            return candidate

    name = (app_name or "").strip()
    if not name:
        return None

    found = shutil.which(name)
    if found:
        p = Path(found)
        if p.is_file():
            return p

    system_root = Path(os.environ.get("SystemRoot", r"C:\Windows"))
    for sub in ("System32", "SysWOW64"):
        cand = system_root / sub / name
        if cand.is_file():
            return cand

    search_roots = [
        Path(os.environ.get("ProgramFiles", r"C:\Program Files")),
        Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")),
        Path.home() / "AppData" / "Local" / "Programs",
        Path.home() / "AppData" / "Local" / "Microsoft" / "WindowsApps",
    ]
    for root in search_roots:
        if not root.is_dir():
            continue
        try:
            direct = root / name
            if direct.is_file():
                return direct
            for child in root.iterdir():
                if not child.is_dir():
                    continue
                cand = child / name
                if cand.is_file():
                    return cand
                try:
                    for nested in child.iterdir():
                        if nested.is_dir():
                            cand2 = nested / name
                            if cand2.is_file():
                                return cand2
                except OSError:
                    pass
        except OSError:
            continue
    return None


def ensure_app_icon(app_name: str | None, app_path: str | None = None) -> Path:
    """Extract and cache a 32x32 PNG icon. Returns cache path or shared placeholder."""
    ensure_data_dirs()
    out = icon_path_for_app(app_name)
    if out.exists() and not is_weak_icon_cache(out):
        return out

    if out.exists() and is_weak_icon_cache(out):
        try:
            out.unlink()
        except OSError:
            pass

    resolved = resolve_exe_path(app_name, app_path)
    if resolved and _extract_exe_icon(resolved, out):
        return out

    return shared_placeholder_path()


def _extract_exe_icon(exe_path: Path, out: Path) -> bool:
    for extractor in (_extract_via_shgetfileinfo, _extract_via_extracticonex):
        try:
            if extractor(exe_path, out) and out.exists() and out.stat().st_size > 0:
                if not is_weak_icon_cache(out):
                    return True
                try:
                    out.unlink()
                except OSError:
                    pass
        except Exception:
            continue
    return False


def _hicon_to_png(hicon: int, out: Path, size: int = 32) -> bool:
    import win32con
    import win32gui
    import win32ui

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


def _extract_via_shgetfileinfo(exe_path: Path, out: Path) -> bool:
    import win32con
    import win32gui

    flags = win32con.SHGFI_ICON | win32con.SHGFI_LARGEICON
    try:
        result = win32gui.SHGetFileInfo(str(exe_path), 0, flags)
    except Exception:
        return False
    hicon = result[0] if isinstance(result, tuple) else getattr(result, "hIcon", 0)
    if not hicon:
        return False
    try:
        return _hicon_to_png(hicon, out)
    finally:
        try:
            win32gui.DestroyIcon(hicon)
        except Exception:
            pass


def _extract_via_extracticonex(exe_path: Path, out: Path) -> bool:
    import win32gui

    large: list = []
    small: list = []
    try:
        large, small = win32gui.ExtractIconEx(str(exe_path), 0)
        handles = large or small
        if not handles:
            return False
        return _hicon_to_png(handles[0], out)
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
