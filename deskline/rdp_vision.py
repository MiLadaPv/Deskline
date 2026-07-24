"""Optional Pro RDP vision: identify apps inside a remote desktop window.

Privacy: off by default. Requires explicit consent + user-owned API key.
Frames are captured only when the foreground app is an RDP client, at most
every rdp_vision_interval_sec, and are not persisted (memory buffer only).
"""

from __future__ import annotations

import base64
import hashlib
import io
import json
import logging
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

from deskline.classify import is_rdp_client

log = logging.getLogger("deskline.rdp_vision")

CONFIDENCE_AUTO_KEEP = 0.55  # below → keep RDP · host without prompting


@dataclass
class VisionSuggestion:
    label: str
    confidence: float
    brand_hint: str | None
    host_hint: str | None
    created_at: float
    session_id: int | None
    frame_hash: str


_pending: VisionSuggestion | None = None
_last_shot_at = 0.0
_last_hash: str | None = None
_busy = False


def get_pending() -> dict[str, Any] | None:
    if not _pending:
        return None
    return {
        "label": _pending.label,
        "confidence": _pending.confidence,
        "brand_hint": _pending.brand_hint,
        "host_hint": _pending.host_hint,
        "created_at": _pending.created_at,
        "session_id": _pending.session_id,
    }


def clear_pending() -> None:
    global _pending
    _pending = None


def vision_enabled(cfg: dict[str, Any], *, is_pro: bool) -> bool:
    if not is_pro:
        return False
    if not cfg.get("rdp_vision_enabled"):
        return False
    if not cfg.get("rdp_vision_consent"):
        return False
    key = str(cfg.get("rdp_vision_api_key") or "").strip()
    return bool(key)


def interval_sec(cfg: dict[str, Any]) -> float:
    raw = float(cfg.get("rdp_vision_interval_sec") or 180)
    return max(120.0, min(300.0, raw))


def _phash(png_bytes: bytes) -> str:
    """Tiny perceptual-ish hash: downsample + average threshold."""
    try:
        from PIL import Image

        img = Image.open(io.BytesIO(png_bytes)).convert("L").resize((16, 16))
        pixels = list(img.getdata())
        avg = sum(pixels) / len(pixels)
        bits = "".join("1" if p >= avg else "0" for p in pixels)
        return hashlib.sha1(bits.encode("ascii")).hexdigest()[:16]
    except Exception:
        return hashlib.sha1(png_bytes).hexdigest()[:16]


def capture_foreground_png(max_side: int = 768) -> bytes | None:
    """Capture the foreground window client area as PNG bytes (no disk write)."""
    try:
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.windll.user32
        hwnd = user32.GetForegroundWindow()
        if not hwnd:
            return None
        rect = wintypes.RECT()
        if not user32.GetWindowRect(hwnd, ctypes.byref(rect)):
            return None
        left, top, right, bottom = rect.left, rect.top, rect.right, rect.bottom
        width = max(0, right - left)
        height = max(0, bottom - top)
        if width < 80 or height < 80:
            return None

        import mss
        from PIL import Image

        with mss.mss() as sct:
            shot = sct.grab({"left": left, "top": top, "width": width, "height": height})
            img = Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")
        # Downscale for cost/privacy surface
        w, h = img.size
        scale = min(1.0, max_side / max(w, h))
        if scale < 1.0:
            img = img.resize((max(1, int(w * scale)), max(1, int(h * scale))), Image.Resampling.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="PNG", optimize=True)
        return buf.getvalue()
    except Exception as exc:
        log.debug("rdp capture failed: %s", exc)
        return None


def _call_vision_api(cfg: dict[str, Any], png_bytes: bytes) -> dict[str, Any] | None:
    api_key = str(cfg.get("rdp_vision_api_key") or "").strip()
    base = str(cfg.get("rdp_vision_base_url") or "https://api.openai.com/v1").rstrip("/")
    model = str(cfg.get("rdp_vision_model") or "gpt-4o-mini").strip()
    if not api_key:
        return None

    b64 = base64.b64encode(png_bytes).decode("ascii")
    prompt = (
        "You see a screenshot of a Windows Remote Desktop session. "
        "Identify the main application or site the user is working in. "
        "Reply with ONLY compact JSON: "
        '{"label":"human name","confidence":0.0-1.0,"brand_hint":"short brand or null"}. '
        "If unsure, use confidence below 0.5 and label like Remote Desktop."
    )
    body = {
        "model": model,
        "temperature": 0,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{b64}"},
                    },
                ],
            }
        ],
    }
    req = urllib.request.Request(
        f"{base}/chat/completions",
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
            "User-Agent": "Deskline-RDP-Vision/0.5",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=25) as resp:
            raw = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError, ValueError) as exc:
        log.warning("rdp vision API error (key redacted): %s", type(exc).__name__)
        return None

    try:
        text = raw["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        return None
    text = (text or "").strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:].strip()
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        # try extract {...}
        start = text.find("{")
        end = text.rfind("}")
        if start < 0 or end <= start:
            return None
        try:
            parsed = json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            return None
    if not isinstance(parsed, dict):
        return None
    label = str(parsed.get("label") or "").strip()[:80]
    if not label:
        return None
    try:
        conf = float(parsed.get("confidence") or 0)
    except (TypeError, ValueError):
        conf = 0.0
    conf = max(0.0, min(1.0, conf))
    brand = parsed.get("brand_hint")
    brand_s = str(brand).strip()[:60] if brand else None
    return {"label": label, "confidence": conf, "brand_hint": brand_s}


def maybe_analyze_rdp(
    cfg: dict[str, Any],
    *,
    app_name: str | None,
    is_pro: bool,
    session_id: int | None,
    host_hint: str | None,
) -> VisionSuggestion | None:
    """Fire-and-forget style sync call; returns suggestion if one should be shown."""
    global _last_shot_at, _last_hash, _pending, _busy

    if not vision_enabled(cfg, is_pro=is_pro):
        return None
    if not is_rdp_client(app_name):
        return None
    if _busy:
        return None
    if _pending:
        return _pending

    now = time.time()
    if now - _last_shot_at < interval_sec(cfg):
        return None

    _busy = True
    try:
        png = capture_foreground_png()
        if not png:
            return None
        frame_hash = _phash(png)
        if frame_hash == _last_hash:
            _last_shot_at = now
            return None
        result = _call_vision_api(cfg, png)
        _last_shot_at = now
        _last_hash = frame_hash
        # Drop image bytes immediately (only hash kept)
        del png
        if not result:
            return None
        if result["confidence"] < CONFIDENCE_AUTO_KEEP:
            # Uncertain → leave RDP · host, no modal
            return None
        suggestion = VisionSuggestion(
            label=result["label"],
            confidence=result["confidence"],
            brand_hint=result.get("brand_hint"),
            host_hint=host_hint,
            created_at=now,
            session_id=session_id,
            frame_hash=frame_hash,
        )
        _pending = suggestion
        return suggestion
    finally:
        _busy = False
