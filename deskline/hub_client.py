from __future__ import annotations

import json
import socket
import urllib.error
import urllib.request
from typing import Any


def push_sessions_to_hub(
    hub_url: str,
    token: str,
    sessions: list[dict[str, Any]],
    *,
    timeout: float = 8.0,
) -> dict[str, Any] | None:
    """POST closed sessions to company hub. Returns response JSON or None on failure."""
    base = (hub_url or "").strip().rstrip("/")
    tok = (token or "").strip()
    if not base or not tok or not sessions:
        return None
    url = f"{base}/api/ingest/sessions"
    body = json.dumps(
        {"hostname": socket.gethostname() or "pc", "sessions": sessions},
        ensure_ascii=False,
    ).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {tok}",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw) if raw else {"ok": True}
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError, json.JSONDecodeError):
        return None
