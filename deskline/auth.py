"""Local Deskline unlock: username + password (multi-user on one PC)."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import secrets
import time
from typing import Any

from deskline.config import DATA_ROOT, ensure_data_dirs

AUTH_PATH = DATA_ROOT / "auth.json"
COOKIE_NAME = "deskline_session"
SESSION_TTL_SEC = 60 * 60 * 12
SESSION_TTL_REMEMBER_SEC = 60 * 60 * 24 * 30
_PBKDF2_ITERATIONS = 200_000
_USERNAME_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{2,31}$")


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


def normalize_username(username: str) -> str:
    return (username or "").strip().lower()


def validate_username(username: str) -> str:
    user = normalize_username(username)
    if not _USERNAME_RE.match(user):
        raise ValueError(
            "Логин: 3–32 символа, латиница/цифры, можно . _ - (с буквы или цифры)"
        )
    return user


def _users(data: dict[str, Any] | None = None) -> dict[str, Any]:
    data = data if data is not None else _load_auth()
    users = data.get("users")
    return users if isinstance(users, dict) else {}


def _legacy_password_hash(data: dict[str, Any] | None = None) -> str | None:
    data = data if data is not None else _load_auth()
    h = data.get("password_hash")
    if isinstance(h, str) and h.startswith("pbkdf2_sha256$"):
        return h
    return None


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
    if _legacy_password_hash(data):
        return True
    for rec in _users(data).values():
        if isinstance(rec, dict):
            h = rec.get("password_hash")
            if isinstance(h, str) and h.startswith("pbkdf2_sha256$"):
                return True
    return False


def list_usernames() -> list[str]:
    return sorted(_users().keys())


def username_exists(username: str) -> bool:
    try:
        user = validate_username(username)
    except ValueError:
        return False
    return user in _users()


def is_google_linked(username: str | None = None) -> bool:
    data = _load_auth()
    if username:
        rec = _users(data).get(normalize_username(username))
        if isinstance(rec, dict):
            sub = rec.get("google_sub")
            return isinstance(sub, str) and bool(sub.strip())
        return False
    # any linked account (status / login gate)
    if isinstance(data.get("google_sub"), str) and data.get("google_sub", "").strip():
        return True
    for rec in _users(data).values():
        if isinstance(rec, dict):
            sub = rec.get("google_sub")
            if isinstance(sub, str) and sub.strip():
                return True
    return False


def google_email(username: str | None = None) -> str | None:
    data = _load_auth()
    if username:
        rec = _users(data).get(normalize_username(username))
        if isinstance(rec, dict):
            email = rec.get("google_email")
            if isinstance(email, str) and email.strip():
                return email.strip()
        return None
    email = data.get("google_email")
    if isinstance(email, str) and email.strip():
        return email.strip()
    for rec in _users(data).values():
        if isinstance(rec, dict):
            e = rec.get("google_email")
            if isinstance(e, str) and e.strip():
                return e.strip()
    return None


def is_auth_configured() -> bool:
    return is_password_set() or is_google_linked()


def link_google_account(sub: str, email: str | None = None, *, username: str | None = None) -> None:
    sub = (sub or "").strip()
    if not sub:
        raise ValueError("missing google sub")
    data = _load_auth()
    user = normalize_username(username) if username else ""
    if user and user in _users(data):
        rec = dict(_users(data)[user])
        existing = rec.get("google_sub")
        if isinstance(existing, str) and existing.strip() and existing.strip() != sub:
            raise PermissionError("another google account is already linked")
        rec["google_sub"] = sub
        if email:
            rec["google_email"] = email.strip()
        data.setdefault("users", {})[user] = rec
    else:
        existing = data.get("google_sub")
        if isinstance(existing, str) and existing.strip() and existing.strip() != sub:
            raise PermissionError("another google account is already linked")
        data["google_sub"] = sub
        if email:
            data["google_email"] = email.strip()
    if not data.get("session_secret"):
        data["session_secret"] = secrets.token_urlsafe(48)
    _save_auth(data)


def unlink_google_account(*, username: str | None = None) -> None:
    data = _load_auth()
    user = normalize_username(username) if username else ""
    if user and user in _users(data):
        rec = dict(_users(data)[user])
        rec.pop("google_sub", None)
        rec.pop("google_email", None)
        data.setdefault("users", {})[user] = rec
    else:
        data.pop("google_sub", None)
        data.pop("google_email", None)
    _save_auth(data)


def verify_google_sub(sub: str) -> bool:
    data = _load_auth()
    linked = data.get("google_sub")
    if isinstance(linked, str) and linked.strip():
        if hmac.compare_digest(linked.strip(), (sub or "").strip()):
            return True
    needle = (sub or "").strip()
    for rec in _users(data).values():
        if isinstance(rec, dict):
            linked = rec.get("google_sub")
            if isinstance(linked, str) and linked.strip():
                if hmac.compare_digest(linked.strip(), needle):
                    return True
    return False


def username_for_google_sub(sub: str) -> str | None:
    needle = (sub or "").strip()
    if not needle:
        return None
    data = _load_auth()
    for name, rec in _users(data).items():
        if isinstance(rec, dict):
            linked = rec.get("google_sub")
            if isinstance(linked, str) and hmac.compare_digest(linked.strip(), needle):
                return str(name)
    return None


def setup_with_google(sub: str, email: str | None = None, *, username: str | None = None) -> str | None:
    """First-run via Google: create user shell if username given."""
    if is_auth_configured() and not username:
        raise ValueError("auth already configured")
    user = ""
    if username:
        user = validate_username(username)
        if username_exists(user):
            raise ValueError("Логин уже зарегистрирован")
    link_google_account(sub, email, username=user or None)
    if user:
        data = _load_auth()
        users = data.setdefault("users", {})
        rec = dict(users.get(user) or {})
        if not rec.get("recovery_hash"):
            recovery_plain = generate_recovery_code()
            rec["recovery_hash"] = hash_password(_normalize_recovery_code(recovery_plain))
            users[user] = rec
            _save_auth(data)
            return recovery_plain
        return None
    if has_recovery_code():
        return None
    data = _load_auth()
    recovery_plain = generate_recovery_code()
    data["recovery_hash"] = hash_password(_normalize_recovery_code(recovery_plain))
    _save_auth(data)
    return recovery_plain


def has_recovery_code(username: str | None = None) -> bool:
    data = _load_auth()
    if username:
        rec = _users(data).get(normalize_username(username))
        if isinstance(rec, dict):
            h = rec.get("recovery_hash")
            return isinstance(h, str) and h.startswith("pbkdf2_sha256$")
        return False
    h = data.get("recovery_hash")
    if isinstance(h, str) and h.startswith("pbkdf2_sha256$"):
        return True
    for rec in _users(data).values():
        if isinstance(rec, dict):
            rh = rec.get("recovery_hash")
            if isinstance(rh, str) and rh.startswith("pbkdf2_sha256$"):
                return True
    return False


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
    if encoded is None:
        data = _load_auth()
        encoded = _legacy_password_hash(data)
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


def verify_recovery_code(code: str, *, username: str | None = None) -> bool:
    data = _load_auth()
    encoded = None
    if username:
        rec = _users(data).get(normalize_username(username))
        if isinstance(rec, dict):
            encoded = rec.get("recovery_hash")
    else:
        encoded = data.get("recovery_hash")
        if not encoded:
            for rec in _users(data).values():
                if isinstance(rec, dict) and isinstance(rec.get("recovery_hash"), str):
                    encoded = rec.get("recovery_hash")
                    break
    if not isinstance(encoded, str) or not encoded.startswith("pbkdf2_sha256$"):
        return False
    normalized = _normalize_recovery_code(code)
    if len(normalized) < 8:
        return False
    return verify_password(normalized, encoded)


def register_user(username: str, password: str, *, issue_recovery: bool = True) -> str | None:
    """Create a new local account. Raises ValueError if username taken/invalid."""
    user = validate_username(username)
    if len(password) < 4:
        raise ValueError("Пароль слишком короткий (минимум 4 символа)")
    data = _load_auth()
    users = data.setdefault("users", {})
    if not isinstance(users, dict):
        users = {}
        data["users"] = users
    if user in users:
        raise ValueError("Логин уже зарегистрирован")
    # Also block if somehow colliding during legacy-only era with same claim later
    rec: dict[str, Any] = {"password_hash": hash_password(password)}
    recovery_plain: str | None = None
    if issue_recovery:
        recovery_plain = generate_recovery_code()
        rec["recovery_hash"] = hash_password(_normalize_recovery_code(recovery_plain))
    users[user] = rec
    if not data.get("session_secret"):
        data["session_secret"] = secrets.token_urlsafe(48)
    # Clear obsolete root password once users exist
    data.pop("password_hash", None)
    if issue_recovery:
        data.pop("recovery_hash", None)
    _save_auth(data)
    return recovery_plain


def set_password(password: str, *, issue_recovery: bool = True, username: str | None = None) -> str | None:
    """Set/replace password for a user (or legacy root if no username yet)."""
    if len(password) < 4:
        raise ValueError("password too short")
    data = _load_auth()
    recovery_plain: str | None = None
    user = normalize_username(username) if username else ""
    if user:
        users = data.setdefault("users", {})
        rec = dict(users.get(user) or {})
        rec["password_hash"] = hash_password(password)
        if issue_recovery or not (
            isinstance(rec.get("recovery_hash"), str)
            and str(rec.get("recovery_hash")).startswith("pbkdf2_sha256$")
        ):
            recovery_plain = generate_recovery_code()
            rec["recovery_hash"] = hash_password(_normalize_recovery_code(recovery_plain))
        users[user] = rec
    else:
        data["password_hash"] = hash_password(password)
        if issue_recovery or not (
            isinstance(data.get("recovery_hash"), str)
            and str(data.get("recovery_hash")).startswith("pbkdf2_sha256$")
        ):
            recovery_plain = generate_recovery_code()
            data["recovery_hash"] = hash_password(_normalize_recovery_code(recovery_plain))
    if not data.get("session_secret"):
        data["session_secret"] = secrets.token_urlsafe(48)
    _save_auth(data)
    return recovery_plain


def authenticate(username: str, password: str) -> str:
    """
    Verify credentials. Returns canonical username.
    Raises LookupError if login missing, PermissionError if bad password,
    ValueError for invalid username format.
    """
    user = validate_username(username)
    data = _load_auth()
    users = _users(data)
    if user in users and isinstance(users[user], dict):
        h = users[user].get("password_hash")
        if not verify_password(password, h if isinstance(h, str) else None):
            raise PermissionError("Неверный пароль")
        return user

    legacy = _legacy_password_hash(data)
    if legacy and verify_password(password, legacy):
        # One-time migrate legacy password-only install into named user
        if user in users:
            raise ValueError("Логин уже зарегистрирован")
        recovery = data.get("recovery_hash")
        rec: dict[str, Any] = {"password_hash": legacy}
        if isinstance(recovery, str):
            rec["recovery_hash"] = recovery
        if isinstance(data.get("google_sub"), str):
            rec["google_sub"] = data["google_sub"]
        if isinstance(data.get("google_email"), str):
            rec["google_email"] = data["google_email"]
        data.setdefault("users", {})[user] = rec
        data.pop("password_hash", None)
        data.pop("recovery_hash", None)
        data.pop("google_sub", None)
        data.pop("google_email", None)
        _save_auth(data)
        return user

    if not users and not legacy:
        raise LookupError("Нет зарегистрированных пользователей")
    raise LookupError("Такого логина нет")


def ensure_recovery_code(username: str | None = None) -> str | None:
    if username and has_recovery_code(username):
        return None
    if not username and has_recovery_code():
        return None
    if username:
        if not username_exists(username):
            return None
        data = _load_auth()
        users = data.setdefault("users", {})
        rec = dict(users.get(normalize_username(username)) or {})
        if not rec.get("password_hash"):
            return None
        recovery_plain = generate_recovery_code()
        rec["recovery_hash"] = hash_password(_normalize_recovery_code(recovery_plain))
        users[normalize_username(username)] = rec
        _save_auth(data)
        return recovery_plain
    if not is_password_set():
        return None
    data = _load_auth()
    recovery_plain = generate_recovery_code()
    data["recovery_hash"] = hash_password(_normalize_recovery_code(recovery_plain))
    _save_auth(data)
    return recovery_plain


def change_password(current: str, new_password: str, *, username: str | None = None) -> str | None:
    user = normalize_username(username) if username else ""
    if user:
        data = _load_auth()
        rec = _users(data).get(user)
        if not isinstance(rec, dict):
            raise PermissionError("bad current password")
        if not verify_password(current, rec.get("password_hash") if isinstance(rec.get("password_hash"), str) else None):
            raise PermissionError("bad current password")
        return set_password(new_password, issue_recovery=True, username=user)
    if not verify_password(current):
        raise PermissionError("bad current password")
    return set_password(new_password, issue_recovery=True)


def reset_password_with_recovery(
    recovery_code: str,
    new_password: str,
    *,
    username: str | None = None,
) -> str:
    user = normalize_username(username) if username else ""
    if user:
        if not username_exists(user):
            raise LookupError("Такого логина нет")
        if not verify_recovery_code(recovery_code, username=user):
            raise PermissionError("bad recovery code")
        code = set_password(new_password, issue_recovery=True, username=user)
        return code or generate_recovery_code()
    if not is_password_set():
        raise ValueError("password not set")
    if not verify_recovery_code(recovery_code):
        raise PermissionError("bad recovery code")
    code = set_password(new_password, issue_recovery=True)
    return code or generate_recovery_code()


def create_session_token(username: str = "", *, remember: bool = False) -> str:
    secret = ensure_session_secret().encode("utf-8")
    ttl = SESSION_TTL_REMEMBER_SEC if remember else SESSION_TTL_SEC
    exp = int(time.time()) + ttl
    nonce = secrets.token_hex(8)
    user = normalize_username(username) if username else "-"
    payload = f"{exp}.{nonce}.{user}"
    sig = hmac.new(secret, payload.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{payload}.{sig}"


def session_username(token: str | None) -> str | None:
    if not token:
        return None
    parts = token.split(".")
    if len(parts) == 4:
        _exp, _nonce, user, _sig = parts
        if user and user != "-" and validate_session_token(token):
            return user
        return None
    return None


def validate_session_token(token: str | None) -> bool:
    if not token:
        return False
    parts = token.split(".")
    # New: exp.nonce.user.sig  |  Legacy: exp.nonce.sig
    if len(parts) == 4:
        exp_s, nonce, user, sig = parts
        payload = f"{exp_s}.{nonce}.{user}"
    elif len(parts) == 3:
        exp_s, nonce, sig = parts
        payload = f"{exp_s}.{nonce}"
    else:
        return False
    if not nonce or not sig:
        return False
    try:
        exp = int(exp_s)
    except ValueError:
        return False
    if exp < int(time.time()):
        return False
    secret = ensure_session_secret().encode("utf-8")
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
        "/docs/compare",
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
