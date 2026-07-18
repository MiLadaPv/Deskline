from __future__ import annotations

from datetime import datetime
from pathlib import Path

import mss
from PIL import Image

from deskline.config import SCREENSHOTS_DIR, ensure_data_dirs


def capture_screenshot(prefix: str = "shot") -> Path:
    """Capture the full virtual desktop and save a JPEG locally."""
    ensure_data_dirs()
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = SCREENSHOTS_DIR / f"{prefix}_{ts}.jpg"
    with mss.mss() as sct:
        monitor = sct.monitors[0]
        shot = sct.grab(monitor)
        img = Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")
        # Shrink large captures for storage
        max_w = 1600
        if img.width > max_w:
            ratio = max_w / img.width
            img = img.resize((max_w, int(img.height * ratio)), Image.Resampling.LANCZOS)
        img.save(out, format="JPEG", quality=72, optimize=True)
    return out
