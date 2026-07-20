from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

import mss
from PIL import Image, ImageFilter

from deskline.config import SCREENSHOTS_DIR, ensure_data_dirs, load_config


def capture_screenshot(prefix: str = "shot") -> Path:
    """Capture the full virtual desktop and save a JPEG locally."""
    ensure_data_dirs()
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = SCREENSHOTS_DIR / f"{prefix}_{ts}.jpg"
    cfg = load_config()
    blur = bool(cfg.get("blur_screenshots"))
    with mss.mss() as sct:
        monitor = sct.monitors[0]
        shot = sct.grab(monitor)
        img = Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")
        max_w = 1600
        if img.width > max_w:
            ratio = max_w / img.width
            img = img.resize((max_w, int(img.height * ratio)), Image.Resampling.LANCZOS)
        if blur:
            # Soft privacy blur (readable layout, not text)
            radius = max(4, img.width // 200)
            img = img.filter(ImageFilter.GaussianBlur(radius=radius))
        img.save(out, format="JPEG", quality=72, optimize=True)
    return out


def delete_screenshot_file(path: str | Path) -> bool:
    p = Path(path)
    try:
        if p.is_file():
            p.unlink()
            return True
    except OSError:
        return False
    return False


def screenshots_storage_info() -> dict[str, Any]:
    ensure_data_dirs()
    files = [p for p in SCREENSHOTS_DIR.iterdir() if p.is_file()]
    total = 0
    for p in files:
        try:
            total += p.stat().st_size
        except OSError:
            pass
    return {
        "path": str(SCREENSHOTS_DIR),
        "count": len(files),
        "bytes": total,
    }
