from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import time
from pathlib import Path
from typing import Any

from deskline.config import DATA_ROOT, ensure_data_dirs

AUTH_PATH = DATA_ROOT / "auth.json"
COOKIE_NAME = "deskline_session"
SESSION_TTL_SEC = 60 * 60 * 12  # 12 hours (browser session cookie by default)
SESSION_TTL_REMEMBER_SEC = 60 * 60 * 24 * 30  # 30 days when "remember me"
_PBKDF2_ITERATIONS = 200_000


def _load_auth() -> dict[str, Any]:
    ensure_data_dirs()
    if not AUTH_PATH.exists():
        return {}
    try:
        raw = json.loads(AUTH_PATH.read_text(encoding="utf-8"))
        return raw if isinstance(raw, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _save_auth(data: dict[str, Any]) -> None:
    ensure_data_dirs()
    AUTH_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")
    try:
        os.chmod(AUTH_PATH, 0o600)
    except OSError:
        pass


def ensure_session_secret() -> str:
    data = _load_auth()
    secret = data.get("session_secret")
    if not isinstance(secret, str) or len(secret) < 32:
        secret = secrets.token_urlsafe(48)
        data["session_secret"] = secret
        _save_auth(data)
    return secret


def is_password_set() -> bool:
    data = _load_auth()
    h = data.get("password_hash")
    return isinstance(h, str) and h.startswith("pbkdf2_sha256$")


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        _PBKDF2_ITERATIONS,
    )
    return f"pbkdf2_sha256${_PBKDF2_ITERATIONS}${salt.hex()}${digest.hex()}"


def verify_password(password: str, encoded: str | None = None) -> bool:
    data = _load_auth()
    encoded = encoded if encoded is not None else data.get("password_hash")
    if not isinstance(encoded, str) or not encoded.startswith("pbkdf2_sha256$"):
        return False
    try:
        _, iter_s, salt_hex, hash_hex = encoded.split("$", 3)
        iterations = int(iter_s)
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(hash_hex)
    except (ValueError, TypeError):
        return False
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        iterations,
    )
    return hmac.compare_digest(digest, expected)


def set_password(password: str) -> None:
    if len(password) < 4:
        raise ValueError("password too short")
    data = _load_auth()
    data["password_hash"] = hash_password(password)
    if not data.get("session_secret"):
        data["session_secret"] = secrets.token_urlsafe(48)
    _save_auth(data)


def change_password(current: str, new_password: str) -> None:
    if not verify_password(current):
        raise PermissionError("bad current password")
    set_password(new_password)


def create_session_token(*, remember: bool = False) -> str:
    secret = ensure_session_secret().encode("utf-8")
    ttl = SESSION_TTL_REMEMBER_SEC if remember else SESSION_TTL_SEC
    exp = int(time.time()) + ttl
    nonce = secrets.token_hex(8)
    payload = f"{exp}.{nonce}"
    sig = hmac.new(secret, payload.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{payload}.{sig}"


def validate_session_token(token: str | None) -> bool:
    if not token or token.count(".") != 2:
        return False
    exp_s, nonce, sig = token.split(".", 2)
    if not nonce or not sig:
        return False
    try:
        exp = int(exp_s)
    except ValueError:
        return False
    if exp < int(time.time()):
        return False
    secret = ensure_session_secret().encode("utf-8")
    payload = f"{exp_s}.{nonce}"
    expected = hmac.new(secret, payload.encode("utf-8"), hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, sig)


def is_public_path(path: str) -> bool:
    if path.startswith("/static/"):
        return True
    if path in {
        "/login",
        "/about",
        "/privacy",
        "/terms",
        "/api/health",
        "/api/auth/status",
        "/api/auth/login",
        "/api/auth/setup",
        "/favicon.ico",
    }:
        return True
    return False
