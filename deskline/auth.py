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


def is_google_linked() -> bool:
    data = _load_auth()
    sub = data.get("google_sub")
    return isinstance(sub, str) and bool(sub.strip())


def google_email() -> str | None:
    data = _load_auth()
    email = data.get("google_email")
    if isinstance(email, str) and email.strip():
        return email.strip()
    return None


def is_auth_configured() -> bool:
    """Local unlock is ready when password or Google account is linked."""
    return is_password_set() or is_google_linked()


def link_google_account(sub: str, email: str | None = None) -> None:
    sub = (sub or "").strip()
    if not sub:
        raise ValueError("missing google sub")
    data = _load_auth()
    existing = data.get("google_sub")
    if isinstance(existing, str) and existing.strip() and existing.strip() != sub:
        raise PermissionError("another google account is already linked")
    data["google_sub"] = sub
    if email:
        data["google_email"] = email.strip()
    if not data.get("session_secret"):
        data["session_secret"] = secrets.token_urlsafe(48)
    _save_auth(data)


def unlink_google_account() -> None:
    data = _load_auth()
    data.pop("google_sub", None)
    data.pop("google_email", None)
    _save_auth(data)


def verify_google_sub(sub: str) -> bool:
    data = _load_auth()
    linked = data.get("google_sub")
    if not isinstance(linked, str) or not linked.strip():
        return False
    return hmac.compare_digest(linked.strip(), (sub or "").strip())


def setup_with_google(sub: str, email: str | None = None) -> str | None:
    """First-run account via Google. Issues recovery code when none exists."""
    if is_auth_configured():
        raise ValueError("auth already configured")
    link_google_account(sub, email)
    if has_recovery_code():
        return None
    data = _load_auth()
    recovery_plain = generate_recovery_code()
    data["recovery_hash"] = hash_password(_normalize_recovery_code(recovery_plain))
    _save_auth(data)
    return recovery_plain


def has_recovery_code() -> bool:
    data = _load_auth()
    h = data.get("recovery_hash")
    return isinstance(h, str) and h.startswith("pbkdf2_sha256$")


def _normalize_recovery_code(code: str) -> str:
    return "".join(ch for ch in (code or "").lower() if ch.isalnum())


def generate_recovery_code() -> str:
    raw = secrets.token_hex(6).upper()
    return f"{raw[0:4]}-{raw[4:8]}-{raw[8:12]}"


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


def verify_recovery_code(code: str) -> bool:
    data = _load_auth()
    encoded = data.get("recovery_hash")
    if not isinstance(encoded, str) or not encoded.startswith("pbkdf2_sha256$"):
        return False
    normalized = _normalize_recovery_code(code)
    if len(normalized) < 8:
        return False
    return verify_password(normalized, encoded)


def set_password(password: str, *, issue_recovery: bool = True) -> str | None:
    if len(password) < 4:
        raise ValueError("password too short")
    data = _load_auth()
    data["password_hash"] = hash_password(password)
    if not data.get("session_secret"):
        data["session_secret"] = secrets.token_urlsafe(48)
    recovery_plain: str | None = None
    if issue_recovery or not (
        isinstance(data.get("recovery_hash"), str)
        and str(data.get("recovery_hash")).startswith("pbkdf2_sha256$")
    ):
        recovery_plain = generate_recovery_code()
        data["recovery_hash"] = hash_password(_normalize_recovery_code(recovery_plain))
    _save_auth(data)
    return recovery_plain


def ensure_recovery_code() -> str | None:
    """Issue a recovery code once if the account has none. Returns plaintext only then."""
    if has_recovery_code():
        return None
    if not is_password_set():
        return None
    data = _load_auth()
    recovery_plain = generate_recovery_code()
    data["recovery_hash"] = hash_password(_normalize_recovery_code(recovery_plain))
    _save_auth(data)
    return recovery_plain


def change_password(current: str, new_password: str) -> str | None:
    if not verify_password(current):
        raise PermissionError("bad current password")
    return set_password(new_password, issue_recovery=True)


def reset_password_with_recovery(recovery_code: str, new_password: str) -> str:
    if not is_password_set():
        raise ValueError("password not set")
    if not verify_recovery_code(recovery_code):
        raise PermissionError("bad recovery code")
    code = set_password(new_password, issue_recovery=True)
    return code or generate_recovery_code()


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
    if path.startswith("/api/ingest"):
        return True
    if path.startswith("/api/extension/"):
        return True
    if path in {
        "/login",
        "/welcome",
        "/logos",
        "/about",
        "/privacy",
        "/terms",
        "/api/health",
        "/api/auth/status",
        "/api/auth/login",
        "/api/auth/setup",
        "/api/auth/recover",
        "/api/auth/google/start",
        "/api/auth/google/callback",
        "/api/license/status",
        "/favicon.ico",
    }:
        return True
    return False
