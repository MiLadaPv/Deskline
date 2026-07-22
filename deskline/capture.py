from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

import mss
from PIL import Image, ImageFilter

from deskline.config import (
    SCREENSHOTS_DIR,
    ensure_data_dirs,
    ensure_screenshots_dir,
    get_screenshots_dir,
    load_config,
)


def capture_screenshot(prefix: str = "shot") -> Path:
    """Capture the full virtual desktop and save a JPEG locally."""
    ensure_data_dirs()
    cfg = load_config()
    shots_dir = ensure_screenshots_dir(cfg)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = shots_dir / f"{prefix}_{ts}.jpg"
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


def resolve_screenshot_file(name: str) -> Path | None:
    """Find a screenshot by filename in the active folder, then the default folder."""
    safe = Path(name).name
    if not safe or safe != name.replace("\\", "/").split("/")[-1]:
        safe = Path(name).name
    candidates = []
    active = get_screenshots_dir()
    candidates.append(active / safe)
    if active.resolve() != SCREENSHOTS_DIR.resolve():
        candidates.append(SCREENSHOTS_DIR / safe)
    for path in candidates:
        if path.is_file():
            return path
    return None


def screenshots_storage_info() -> dict[str, Any]:
    ensure_data_dirs()
    shots_dir = ensure_screenshots_dir()
    files = [p for p in shots_dir.iterdir() if p.is_file()]
    total = 0
    for p in files:
        try:
            total += p.stat().st_size
        except OSError:
            pass
    return {
        "path": str(shots_dir),
        "count": len(files),
        "bytes": total,
    }
