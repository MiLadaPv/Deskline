from __future__ import annotations

import io
import os
import re
import shutil
import urllib.error
import urllib.request
from pathlib import Path

from PIL import Image, ImageDraw

from deskline.config import ICONS_DIR, ensure_data_dirs

_SAFE_NAME = re.compile(r"[^a-zA-Z0-9._-]+")
# Placeholder PNGs from the old buggy cache are ~200 bytes; real icons are larger.
_WEAK_CACHE_MAX_BYTES = 400
_PLACEHOLDER_NAME = "placeholder.png"
_SITE_PREFIX = "site_"
_FAVICON_TIMEOUT_SEC = 3.0


def icon_cache_name(app_name: str) -> str:
    base = (app_name or "unknown.exe").strip().lower()
    safe = _SAFE_NAME.sub("_", base)
    if not safe.endswith(".png"):
        safe = f"{safe}.png"
    return safe


def icon_cache_name_for_site(site: str) -> str:
    host = (site or "unknown").strip().lower()
    if host.startswith("www."):
        host = host[4:]
    safe = _SAFE_NAME.sub("_", host)
    return f"{_SITE_PREFIX}{safe}.png"


def icon_url_for_app(app_name: str | None) -> str:
    name = icon_cache_name(app_name or "unknown.exe")
    return f"/media/icons/{name}"


def icon_url_for_site(site: str | None) -> str:
    name = icon_cache_name_for_site(site or "unknown")
    return f"/media/icons/{name}"


def icon_path_for_app(app_name: str | None) -> Path:
    ensure_data_dirs()
    return ICONS_DIR / icon_cache_name(app_name or "unknown.exe")


def icon_path_for_site(site: str | None) -> Path:
    ensure_data_dirs()
    return ICONS_DIR / icon_cache_name_for_site(site or "unknown")


def is_site_icon_name(name: str) -> bool:
    return (name or "").startswith(_SITE_PREFIX)


def site_from_icon_name(name: str) -> str | None:
    """Recover domain from a site_*.png cache filename."""
    safe = Path(name).name
    if not safe.startswith(_SITE_PREFIX):
        return None
    stem = safe[len(_SITE_PREFIX) :]
    if stem.endswith(".png"):
        stem = stem[:-4]
    return stem.replace("_", ".") or None


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
    # Site favicons are often tiny solid PNGs; do not treat them as weak by size.
    if path.name.startswith(_SITE_PREFIX):
        return False
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
        # DisplayIcon-style "C:\\app.exe,0"
        if "," in app_path:
            stripped = Path(app_path.split(",", 1)[0].strip().strip('"'))
            if stripped.is_file():
                return stripped

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

    via_reg = _resolve_via_registry(name)
    if via_reg:
        return via_reg

    search_roots = [
        Path(os.environ.get("ProgramFiles", r"C:\Program Files")),
        Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")),
        Path.home() / "AppData" / "Local" / "Programs",
        Path.home() / "AppData" / "Local" / "Microsoft" / "WindowsApps",
        Path(r"C:\OneDriveTemp"),
        Path.home() / "OneDrive",
        Path.home() / "Desktop",
        Path.home() / "Downloads",
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


def _resolve_via_registry(name: str) -> Path | None:
    """Find exe via App Paths and Uninstall DisplayIcon/InstallLocation."""
    try:
        import winreg
    except ImportError:
        return None

    name_l = name.lower()
    for hive in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
        try:
            with winreg.OpenKey(
                hive, rf"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\{name}"
            ) as key:
                val, _ = winreg.QueryValueEx(key, None)
                path = _path_from_reg_value(str(val))
                if path:
                    return path
        except OSError:
            pass

    uninstall_keys = [
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
    ]
    for hive, sub in uninstall_keys:
        try:
            with winreg.OpenKey(hive, sub) as parent:
                idx = 0
                while True:
                    try:
                        child_name = winreg.EnumKey(parent, idx)
                    except OSError:
                        break
                    idx += 1
                    try:
                        with winreg.OpenKey(parent, child_name) as key:
                            path = _path_from_uninstall_key(key, name_l)
                            if path:
                                return path
                    except OSError:
                        continue
        except OSError:
            continue
    return None


def _path_from_reg_value(value: str) -> Path | None:
    raw = (value or "").strip().strip('"')
    if not raw:
        return None
    if "," in raw and not Path(raw).is_file():
        raw = raw.split(",", 1)[0].strip().strip('"')
    path = Path(raw)
    return path if path.is_file() else None


def _path_from_uninstall_key(key, name_l: str) -> Path | None:
    import winreg

    icon = None
    location = None
    try:
        icon, _ = winreg.QueryValueEx(key, "DisplayIcon")
    except OSError:
        pass
    try:
        location, _ = winreg.QueryValueEx(key, "InstallLocation")
    except OSError:
        pass

    if icon:
        path = _path_from_reg_value(str(icon))
        if path and path.name.lower() == name_l:
            return path

    if location:
        cand = Path(str(location).strip().strip('"')) / name_l
        if cand.is_file():
            return cand
        # Case-preserving search in install folder
        if cand.parent.is_dir():
            try:
                for child in cand.parent.iterdir():
                    if child.is_file() and child.name.lower() == name_l:
                        return child
            except OSError:
                pass
    return None


def _trim_and_fit(img: Image.Image, size: int = 32, padding: int = 2) -> Image.Image:
    """Crop transparent padding and fit content into a size×size canvas."""
    rgba = img.convert("RGBA")
    bbox = rgba.getbbox()
    if bbox:
        rgba = rgba.crop(bbox)
    inner = max(1, size - 2 * padding)
    w, h = rgba.size
    scale = min(inner / max(w, 1), inner / max(h, 1))
    new_w = max(1, int(round(w * scale)))
    new_h = max(1, int(round(h * scale)))
    rgba = rgba.resize((new_w, new_h), Image.Resampling.LANCZOS)
    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    ox = (size - new_w) // 2
    oy = (size - new_h) // 2
    canvas.paste(rgba, (ox, oy), rgba)
    return canvas


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


def ensure_site_icon(site: str | None) -> Path:
    """Fetch and cache a site favicon as 32x32 PNG. Returns cache path or placeholder."""
    ensure_data_dirs()
    host = (site or "").strip().lower()
    if host.startswith("www."):
        host = host[4:]
    if not host or " " in host or "." not in host:
        return shared_placeholder_path()

    out = icon_path_for_site(host)
    if out.exists() and not is_weak_icon_cache(out):
        return out

    if out.exists() and is_weak_icon_cache(out):
        try:
            out.unlink()
        except OSError:
            pass

    if _fetch_site_favicon(host, out):
        return out
    return shared_placeholder_path()


def _fetch_site_favicon(host: str, out: Path) -> bool:
    urls = [
        f"https://{host}/favicon.ico",
        f"https://www.google.com/s2/favicons?domain={host}&sz=64",
    ]
    for url in urls:
        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "Deskline/0.2"},
                method="GET",
            )
            with urllib.request.urlopen(req, timeout=_FAVICON_TIMEOUT_SEC) as resp:
                data = resp.read()
            if not data or len(data) < 16:
                continue
            if _bytes_to_icon_png(data, out):
                return True
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError, ValueError):
            continue
        except Exception:
            continue
    return False


def _bytes_to_icon_png(data: bytes, out: Path, size: int = 32) -> bool:
    try:
        img = Image.open(io.BytesIO(data))
        img = _trim_and_fit(img, size=size, padding=2)
        img.save(out, format="PNG")
        return out.exists() and out.stat().st_size > 0
    except Exception:
        return False


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

    # Draw larger then trim so content fills the final cell
    draw_size = max(size * 2, 64)
    hdc = win32ui.CreateDCFromHandle(win32gui.GetDC(0))
    hbmp = win32ui.CreateBitmap()
    hbmp.CreateCompatibleBitmap(hdc, draw_size, draw_size)
    hdc_mem = hdc.CreateCompatibleDC()
    hdc_mem.SelectObject(hbmp)
    try:
        hdc_mem.DrawIconEx(
            (0, 0),
            hicon,
            draw_size,
            draw_size,
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
    img = _trim_and_fit(img, size=size, padding=2)
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
