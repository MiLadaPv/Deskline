"""Local license.json persistence with HMAC integrity check."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
from pathlib import Path
from typing import Any

from deskline.config import DATA_ROOT, ensure_data_dirs

LICENSE_PATH = DATA_ROOT / "license.json"

# Public verify material only — not a Lemon Squeezy secret.
# Used to detect local tampering of the cached license file.
_LICENSE_HMAC_SALT = b"deskline-license-v1-andalusgames"


def _hmac_key() -> bytes:
    extra = os.environ.get("DESKLINE_LICENSE_HMAC_SECRET", "").encode("utf-8")
    return hashlib.sha256(_LICENSE_HMAC_SALT + extra).digest()


def _sign(payload: dict[str, Any]) -> str:
    body = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hmac.new(_hmac_key(), body, hashlib.sha256).hexdigest()


def load_license() -> dict[str, Any] | None:
    ensure_data_dirs()
    if not LICENSE_PATH.exists():
        return None
    try:
        raw = json.loads(LICENSE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(raw, dict):
        return None
    sig = raw.get("signature")
    payload = {k: v for k, v in raw.items() if k != "signature"}
    if not isinstance(sig, str) or not hmac.compare_digest(_sign(payload), sig):
        return None
    return payload


def save_license(payload: dict[str, Any]) -> dict[str, Any]:
    ensure_data_dirs()
    clean = {k: v for k, v in payload.items() if k != "signature"}
    clean["signature"] = _sign(clean)
    LICENSE_PATH.write_text(json.dumps(clean, indent=2), encoding="utf-8")
    try:
        os.chmod(LICENSE_PATH, 0o600)
    except OSError:
        pass
    return {k: v for k, v in clean.items() if k != "signature"}


def clear_license() -> None:
    try:
        LICENSE_PATH.unlink(missing_ok=True)
    except OSError:
        pass


def license_path() -> Path:
    return LICENSE_PATH
