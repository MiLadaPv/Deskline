"""Extract chat/call peer names from Deskline screenshots via vision API."""

from __future__ import annotations

import base64
import json
import logging
import re
import urllib.error
import urllib.request
from datetime import date
from pathlib import Path
from typing import Any

log = logging.getLogger("deskline.meetings_vision")

_NOISE_PEER = re.compile(
    r"^(?:"
    r"поиск|search|настройк\w*|settings|меню|menu|чаты|chats|контакты|contacts|"
    r"я|you|me|deskline|microsoft\s*edge|google\s*chrome|"
    r"нов\w*\s+сообщени\w*|unread|"
    r"яндекс\s*мессенджер|yandex\s*messenger|телемост|telemost|teams|zoom"
    r")$",
    re.IGNORECASE,
)


def _shot_matches_channel(row: dict[str, Any], channel_key: str | None) -> bool:
    blob = " ".join(
        str(row.get(k) or "")
        for k in ("activity_label", "window_title", "display_name", "app_name")
    ).casefold()
    key = str(channel_key or "").casefold()
    if key.startswith("site:messenger.yandex.ru") or "messenger" in key:
        return any(tok in blob for tok in ("мессенджер", "messenger.yandex", "yandex messenger"))
    if key.startswith("site:telemost.yandex.ru") or "telemost" in key:
        return any(tok in blob for tok in ("телемост", "telemost"))
    if key.startswith("site:discord.com") or "discord" in key:
        return "discord" in blob
    if key.startswith("app:"):
        exe = key.split(":", 1)[-1]
        app = str(row.get("app_name") or "").casefold()
        return exe in app or app.endswith(exe)
    # Generic: prefer chat/meeting-looking shots
    return any(
        tok in blob
        for tok in (
            "мессенджер",
            "messenger",
            "телемост",
            "telemost",
            "teams",
            "zoom",
            "meet",
            "discord",
            "skype",
        )
    )


def find_latest_channel_screenshot(
    db: Any,
    *,
    channel_key: str | None = None,
    day: date | None = None,
) -> dict[str, Any] | None:
    rows = db.screenshots_for_date(day or date.today())
    for row in rows:
        if not _shot_matches_channel(row, channel_key):
            continue
        path = Path(str(row.get("path") or ""))
        if path.is_file() and path.stat().st_size > 800:
            out = dict(row)
            out["path"] = str(path)
            return out
    return None


def _call_peers_vision(cfg: dict[str, Any], image_bytes: bytes) -> dict[str, Any] | None:
    api_key = str(cfg.get("rdp_vision_api_key") or "").strip()
    base = str(cfg.get("rdp_vision_base_url") or "https://api.openai.com/v1").rstrip("/")
    model = str(cfg.get("rdp_vision_model") or "gpt-4o-mini").strip()
    if not api_key:
        return None

    b64 = base64.b64encode(image_bytes).decode("ascii")
    prompt = (
        "This is a screenshot of a messenger, chat, or video call UI. "
        "Extract the human participant name(s) of the active conversation or call "
        "(the person/people the user is chatting or speaking with). "
        "Ignore UI chrome: Search, Settings, Chats, unread counters, browser chrome, "
        "app brand names. "
        'Reply with ONLY compact JSON: '
        '{"peers":["Name"],"kind":"chat"|"call"|"group"|"unknown","confidence":0.0-1.0}. '
        "If no person name is visible, return peers:[]."
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
                        "image_url": {"url": f"data:image/jpeg;base64,{b64}"},
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
            "User-Agent": "Deskline-Meetings-Vision/0.5",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError, ValueError) as exc:
        log.warning("meetings peers vision API error: %s", type(exc).__name__)
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
        return None
    if not isinstance(parsed, dict):
        return None
    peers_raw = parsed.get("peers") or []
    peers: list[str] = []
    if isinstance(peers_raw, list):
        for p in peers_raw:
            name = str(p or "").strip()
            if len(name) < 2 or len(name) > 80:
                continue
            if _NOISE_PEER.match(name):
                continue
            if name not in peers:
                peers.append(name)
    kind = str(parsed.get("kind") or "unknown").strip().lower()
    if kind not in {"chat", "call", "group", "unknown"}:
        kind = "unknown"
    try:
        confidence = float(parsed.get("confidence") or 0)
    except (TypeError, ValueError):
        confidence = 0.0
    return {"peers": peers[:8], "kind": kind, "confidence": max(0.0, min(1.0, confidence))}


def extract_peers_from_screenshot(
    cfg: dict[str, Any],
    image_path: str | Path,
) -> dict[str, Any]:
    path = Path(image_path)
    if not path.is_file():
        return {"ok": False, "error": "screenshot_missing", "peers": []}
    try:
        data = path.read_bytes()
    except OSError:
        return {"ok": False, "error": "screenshot_unreadable", "peers": []}
    if len(data) < 800:
        return {"ok": False, "error": "screenshot_empty", "peers": []}
    if not str(cfg.get("rdp_vision_api_key") or "").strip():
        return {"ok": False, "error": "vision_key_missing", "peers": []}
    parsed = _call_peers_vision(cfg, data)
    if not parsed:
        return {"ok": False, "error": "vision_failed", "peers": []}
    return {
        "ok": True,
        "peers": [
            {"name": n, "sec": 0, "kind": "group" if parsed["kind"] == "group" else "dm"}
            for n in parsed["peers"]
        ],
        "kind": parsed["kind"],
        "confidence": parsed["confidence"],
        "source": "screenshot",
        "path": str(path),
    }
