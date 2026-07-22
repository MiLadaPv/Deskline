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
_APP_ICON_PADDING = 5
_SITE_ICON_PADDING = 2
_APP_ICON_MAX_FILL = 0.88
# Bump when extractor changes so old HTTP/disk caches are abandoned.
_APP_ICON_REV = "v2"

# Extra favicon URLs for hosts where /favicon.ico and Google s2 fail.
_SITE_FAVICON_OVERRIDES: dict[str, list[str]] = {
    "messenger.yandex.ru": [
        "https://favicon.yandex.net/favicon/v2/messenger.yandex.ru?size=32",
        "https://yandex.ru/favicon.ico",
    ],
    "mail.yandex.ru": [
        "https://favicon.yandex.net/favicon/v2/mail.yandex.ru?size=32",
        "https://yandex.ru/favicon.ico",
    ],
}


def icon_cache_name(app_name: str) -> str:
    base = (app_name or "unknown.exe").strip().lower()
    safe = _SAFE_NAME.sub("_", base)
    if safe.endswith(".png"):
        safe = safe[:-4]
    # Drop a trailing rev if present so we don't stack .v2.v2
    rev_suffix = f".{_APP_ICON_REV}"
    if safe.endswith(rev_suffix):
        safe = safe[: -len(rev_suffix)]
    return f"{safe}.{_APP_ICON_REV}.png"


def icon_cache_name_for_site(site: str) -> str:
    host = (site or "unknown").strip().lower()
    if host.startswith("www."):
        host = host[4:]
    safe = _SAFE_NAME.sub("_", host)
    return f"{_SITE_PREFIX}{safe}.png"


def app_name_from_icon_filename(name: str) -> str | None:
    """Recover exe name from msedge.exe.v2.png (not site_/placeholder)."""
    safe = Path(name).name
    if safe == _PLACEHOLDER_NAME or safe.startswith(_SITE_PREFIX):
        return None
    if not safe.endswith(".png"):
        return None
    stem = safe[:-4]
    rev_suffix = f".{_APP_ICON_REV}"
    if stem.endswith(rev_suffix):
        stem = stem[: -len(rev_suffix)]
    return stem or None


def _cache_bust_qs(path: Path) -> str:
    if path.exists():
        try:
            return str(int(path.stat().st_mtime))
        except OSError:
            pass
    return _APP_ICON_REV


def icon_url_for_app(app_name: str | None) -> str:
    name = icon_cache_name(app_name or "unknown.exe")
    path = ICONS_DIR / name
    return f"/media/icons/{name}?v={_cache_bust_qs(path)}"


def icon_url_for_site(site: str | None) -> str:
    name = icon_cache_name_for_site(site or "unknown")
    path = ICONS_DIR / name
    return f"/media/icons/{name}?v={_cache_bust_qs(path)}"


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


def is_placeholder_path(path: Path | None) -> bool:
    return bool(path) and Path(path).name == _PLACEHOLDER_NAME


def resolve_icon_url(site: str | None = None, app_name: str | None = None) -> str:
    """Prefer a cached site favicon; fall back to the app icon URL.

    Does not download favicons here — /media/icons fetches on demand so
    summary/list APIs stay fast.
    """
    if site:
        path = icon_path_for_site(site)
        if path.exists() and not is_placeholder_path(path) and not is_weak_icon_cache(path):
            return icon_url_for_site(site)
    if app_name:
        return icon_url_for_app(app_name)
    return icon_url_for_app("unknown.exe")


def is_weak_icon_cache(path: Path) -> bool:
    """True if missing, empty, blank, or a Deskline placeholder left by a failed extract."""
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
    if path.name.startswith(_SITE_PREFIX):
        return _cached_icon_is_blank(path)
    # Legacy per-app placeholders were a solid teal circle (~110–220 bytes).
    if size <= 220:
        return True
    # Old extracts with padding=2 fill the cell and look cropped in the UI — re-extract.
    if _app_icon_too_tight(path):
        return True
    return False


def purge_placeholder_icons() -> int:
    """Remove weak/legacy icon PNGs so real icons can be re-extracted."""
    ensure_data_dirs()
    removed = 0
    rev_tail = f".{_APP_ICON_REV}.png"
    for path in ICONS_DIR.glob("*.png"):
        if path.name == _PLACEHOLDER_NAME:
            continue
        # Drop pre-v2 app icons (msedge.exe.png) so DIB extractor rebuilds them.
        if (
            not path.name.startswith(_SITE_PREFIX)
            and not path.name.endswith(rev_tail)
        ):
            try:
                path.unlink()
                removed += 1
            except OSError:
                pass
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


def _trim_and_fit(
    img: Image.Image,
    size: int = 32,
    padding: int = 2,
    max_fill: float = 1.0,
) -> Image.Image:
    """Crop transparent padding and fit content into a size×size canvas."""
    rgba = img.convert("RGBA")
    bbox = rgba.getbbox()
    if bbox:
        rgba = rgba.crop(bbox)
    inner = max(1, size - 2 * padding)
    w, h = rgba.size
    scale = min(inner / max(w, 1), inner / max(h, 1))
    if max_fill < 1.0:
        scale = min(scale, float(max_fill))
    new_w = max(1, int(round(w * scale)))
    new_h = max(1, int(round(h * scale)))
    rgba = rgba.resize((new_w, new_h), Image.Resampling.LANCZOS)
    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    ox = (size - new_w) // 2
    oy = (size - new_h) // 2
    canvas.paste(rgba, (ox, oy), rgba)
    return canvas


def _icon_has_usable_content(img: Image.Image, min_side: int = 8) -> bool:
    """Reject fully transparent / 1×1 / near-empty favicons."""
    try:
        rgba = img.convert("RGBA")
    except Exception:
        return False
    bbox = rgba.getbbox()
    if not bbox:
        return False
    w = bbox[2] - bbox[0]
    h = bbox[3] - bbox[1]
    if w < min_side or h < min_side:
        return False
    alpha = rgba.split()[3]
    hist = alpha.histogram()
    opaque = sum(hist[32:])  # alpha >= 32
    return opaque >= 16


def _cached_icon_is_blank(path: Path) -> bool:
    try:
        with Image.open(path) as img:
            return not _icon_has_usable_content(img)
    except Exception:
        return True


def _app_icon_too_tight(path: Path, margin: int = 1) -> bool:
    """True when content touches the canvas edge (old padding=2 extracts)."""
    try:
        with Image.open(path) as img:
            rgba = img.convert("RGBA")
            bbox = rgba.getbbox()
            if not bbox:
                return True
            w, h = rgba.size
            return (
                bbox[0] <= margin
                or bbox[1] <= margin
                or bbox[2] >= w - margin
                or bbox[3] >= h - margin
            )
    except Exception:
        return False


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
    urls: list[str] = []
    urls.extend(_SITE_FAVICON_OVERRIDES.get(host, []))
    urls.extend(
        [
            f"https://{host}/favicon.ico",
            f"https://www.google.com/s2/favicons?domain={host}&sz=64",
            f"https://favicon.yandex.net/favicon/v2/{host}?size=32",
        ]
    )
    # Apex fallback for subdomains (messenger.yandex.ru → yandex.ru)
    parts = host.split(".")
    if len(parts) > 2:
        apex = ".".join(parts[-2:])
        if apex != host:
            urls.append(f"https://{apex}/favicon.ico")
            urls.append(f"https://favicon.yandex.net/favicon/v2/{apex}?size=32")
            urls.append(f"https://www.google.com/s2/favicons?domain={apex}&sz=64")

    seen: set[str] = set()
    for url in urls:
        if url in seen:
            continue
        seen.add(url)
        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "Deskline/0.4"},
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
        if not _icon_has_usable_content(img):
            return False
        img = _trim_and_fit(img, size=size, padding=_SITE_ICON_PADDING)
        if not _icon_has_usable_content(img, min_side=6):
            return False
        img.save(out, format="PNG")
        return out.exists() and out.stat().st_size > 0 and not _cached_icon_is_blank(out)
    except Exception:
        return False


def _restore_alpha_if_needed(img: Image.Image) -> Image.Image:
    """GDI often draws RGB with alpha left at 0 — treat non-black RGB as opaque."""
    rgba = img.convert("RGBA")
    pixels = list(rgba.getdata())
    if not pixels:
        return rgba
    max_a = max(p[3] for p in pixels)
    if max_a > 10:
        return rgba
    fixed = [
        (r, g, b, 255) if (r or g or b) else (0, 0, 0, 0)
        for r, g, b, a in pixels
    ]
    rgba.putdata(fixed)
    return rgba


def _extract_exe_icon(exe_path: Path, out: Path) -> bool:
    for extractor in (
        _extract_via_private_extract,
        _extract_via_shgetfileinfo,
        _extract_via_extracticonex,
    ):
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


def _hicon_to_png(hicon: int, out: Path, size: int = 32, draw_size: int | None = None) -> bool:
    """Rasterize HICON via a 32bpp top-down DIB (reliable alpha vs CreateCompatibleBitmap)."""
    import ctypes
    from ctypes import wintypes

    import win32con

    draw = int(draw_size or max(size * 8, 256))

    class BITMAPINFOHEADER(ctypes.Structure):
        _fields_ = [
            ("biSize", wintypes.DWORD),
            ("biWidth", wintypes.LONG),
            ("biHeight", wintypes.LONG),
            ("biPlanes", wintypes.WORD),
            ("biBitCount", wintypes.WORD),
            ("biCompression", wintypes.DWORD),
            ("biSizeImage", wintypes.DWORD),
            ("biXPelsPerMeter", wintypes.LONG),
            ("biYPelsPerMeter", wintypes.LONG),
            ("biClrUsed", wintypes.DWORD),
            ("biClrImportant", wintypes.DWORD),
        ]

    class BITMAPINFO(ctypes.Structure):
        _fields_ = [
            ("bmiHeader", BITMAPINFOHEADER),
            ("bmiColors", wintypes.DWORD * 3),
        ]

    user32 = ctypes.windll.user32
    gdi32 = ctypes.windll.gdi32

    hdc_screen = user32.GetDC(0)
    if not hdc_screen:
        return False
    hdc = gdi32.CreateCompatibleDC(hdc_screen)
    if not hdc:
        user32.ReleaseDC(0, hdc_screen)
        return False

    bmi = BITMAPINFO()
    ctypes.memset(ctypes.byref(bmi), 0, ctypes.sizeof(bmi))
    bmi.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
    bmi.bmiHeader.biWidth = draw
    bmi.bmiHeader.biHeight = -draw  # top-down
    bmi.bmiHeader.biPlanes = 1
    bmi.bmiHeader.biBitCount = 32
    bmi.bmiHeader.biCompression = 0  # BI_RGB

    bits_ptr = ctypes.c_void_p()
    hbmp = gdi32.CreateDIBSection(
        hdc,
        ctypes.byref(bmi),
        0,  # DIB_RGB_COLORS
        ctypes.byref(bits_ptr),
        None,
        0,
    )
    if not hbmp or not bits_ptr.value:
        gdi32.DeleteDC(hdc)
        user32.ReleaseDC(0, hdc_screen)
        return False

    old = gdi32.SelectObject(hdc, hbmp)
    try:
        byte_count = draw * draw * 4
        ctypes.memset(bits_ptr, 0, byte_count)
        ok = user32.DrawIconEx(
            hdc,
            0,
            0,
            hicon,
            draw,
            draw,
            0,
            None,
            win32con.DI_NORMAL,
        )
        if not ok:
            return False
        raw = ctypes.string_at(bits_ptr, byte_count)
        img = Image.frombuffer("RGBA", (draw, draw), raw, "raw", "BGRA", 0, 1).copy()
        img = _restore_alpha_if_needed(img)
        if not _icon_has_usable_content(img, min_side=4):
            return False
        img = _trim_and_fit(
            img,
            size=size,
            padding=_APP_ICON_PADDING,
            max_fill=_APP_ICON_MAX_FILL,
        )
        img.save(out, format="PNG")
        return out.exists() and out.stat().st_size > 0 and not is_weak_icon_cache(out)
    finally:
        gdi32.SelectObject(hdc, old)
        gdi32.DeleteObject(hbmp)
        gdi32.DeleteDC(hdc)
        user32.ReleaseDC(0, hdc_screen)


def _extract_via_private_extract(exe_path: Path, out: Path) -> bool:
    """Prefer native high-res icons (avoids stretch from tiny 16px shells)."""
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.windll.user32
    large = (wintypes.HANDLE * 1)()
    icon_ids = (wintypes.UINT * 1)()
    for dim in (256, 128, 48, 32):
        large[0] = 0
        n = user32.PrivateExtractIconsW(
            str(exe_path),
            0,
            dim,
            dim,
            large,
            icon_ids,
            1,
            0,
        )
        hicon = int(large[0] or 0)
        if not n or not hicon:
            continue
        try:
            if _hicon_to_png(hicon, out, size=32, draw_size=max(dim, 64)):
                return True
        finally:
            try:
                user32.DestroyIcon(hicon)
            except Exception:
                pass
    return False


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
