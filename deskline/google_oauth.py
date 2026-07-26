"""Optional Google OAuth (OIDC) unlock for local Deskline."""

from __future__ import annotations

import base64
import hashlib
import json
import os
import secrets
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from deskline.config import DATA_ROOT, ensure_data_dirs

GOOGLE_AUTH_URI = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URI = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URI = "https://openidconnect.googleapis.com/v1/userinfo"
OAUTH_SCOPES = "openid email profile"
OAUTH_STATE_COOKIE = "deskline_oauth"
OAUTH_JSON_NAME = "google-oauth.json"
REDIRECT_PATH = "/api/auth/google/callback"
OAUTH_PENDING_DIRNAME = "oauth_pending"
OAUTH_FINISH_DIRNAME = "oauth_finish"


@dataclass(frozen=True)
class GoogleOAuthConfig:
    client_id: str
    client_secret: str
    token_uri: str = GOOGLE_TOKEN_URI
    auth_uri: str = GOOGLE_AUTH_URI


def redirect_uri() -> str:
    """Loopback URI Google Desktop/Web clients accept.

    Prefer localhost (matches typical Desktop client JSON) over 127.0.0.1.
    Override with DESKLINE_GOOGLE_REDIRECT_URI if needed.
    """
    override = (os.environ.get("DESKLINE_GOOGLE_REDIRECT_URI") or "").strip()
    if override:
        return override
    from deskline.config import PORT

    return f"http://localhost:{PORT}{REDIRECT_PATH}"


def _pending_dir() -> Path:
    ensure_data_dirs()
    path = DATA_ROOT / OAUTH_PENDING_DIRNAME
    path.mkdir(parents=True, exist_ok=True)
    return path


def save_oauth_pending(state: str, *, verifier: str, bind: bool) -> None:
    path = _pending_dir() / f"{state}.json"
    path.write_text(
        json.dumps(
            {
                "verifier": verifier,
                "bind": bool(bind),
                "exp": int(time.time()) + 600,
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def pop_oauth_pending(state: str) -> dict[str, Any] | None:
    path = _pending_dir() / f"{state}.json"
    if not path.is_file():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        raw = None
    try:
        path.unlink(missing_ok=True)
    except OSError:
        pass
    if not isinstance(raw, dict):
        return None
    try:
        exp = int(raw.get("exp") or 0)
    except (TypeError, ValueError):
        return None
    if exp < int(time.time()):
        return None
    return raw


def app_origin() -> str:
    """Canonical UI origin (Tauri/tray use 127.0.0.1; OAuth callback uses localhost)."""
    from deskline.config import BASE_URL

    return BASE_URL.rstrip("/")


def _finish_dir() -> Path:
    ensure_data_dirs()
    path = DATA_ROOT / OAUTH_FINISH_DIRNAME
    path.mkdir(parents=True, exist_ok=True)
    return path


def save_oauth_finish_ticket(
    *,
    session_token: str,
    recovery_code: str | None = None,
    want_bind: bool = False,
) -> str:
    """One-time ticket so session cookie is set on app_origin, not localhost."""
    ticket = secrets.token_urlsafe(32)
    path = _finish_dir() / f"{ticket}.json"
    path.write_text(
        json.dumps(
            {
                "session_token": session_token,
                "recovery_code": recovery_code,
                "want_bind": bool(want_bind),
                "exp": int(time.time()) + 120,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return ticket


def pop_oauth_finish_ticket(ticket: str) -> dict[str, Any] | None:
    ticket = (ticket or "").strip()
    if not ticket or "/" in ticket or "\\" in ticket or ".." in ticket:
        return None
    path = _finish_dir() / f"{ticket}.json"
    if not path.is_file():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        raw = None
    try:
        path.unlink(missing_ok=True)
    except OSError:
        pass
    if not isinstance(raw, dict):
        return None
    try:
        exp = int(raw.get("exp") or 0)
    except (TypeError, ValueError):
        return None
    if exp < int(time.time()):
        return None
    token = raw.get("session_token")
    if not isinstance(token, str) or not token.strip():
        return None
    return raw


def _parse_oauth_dict(raw: dict[str, Any]) -> GoogleOAuthConfig | None:
    block = raw.get("installed") or raw.get("web") or raw
    if not isinstance(block, dict):
        return None
    client_id = str(block.get("client_id") or "").strip()
    client_secret = str(block.get("client_secret") or "").strip()
    if not client_id or not client_secret:
        return None
    return GoogleOAuthConfig(
        client_id=client_id,
        client_secret=client_secret,
        token_uri=str(block.get("token_uri") or GOOGLE_TOKEN_URI),
        auth_uri=str(block.get("auth_uri") or GOOGLE_AUTH_URI),
    )


def load_google_oauth_config() -> GoogleOAuthConfig | None:
    """Load Client ID/secret from env or %LOCALAPPDATA%\\Deskline\\google-oauth.json."""
    env_id = (os.environ.get("DESKLINE_GOOGLE_CLIENT_ID") or "").strip()
    env_secret = (os.environ.get("DESKLINE_GOOGLE_CLIENT_SECRET") or "").strip()
    if env_id and env_secret:
        return GoogleOAuthConfig(client_id=env_id, client_secret=env_secret)

    ensure_data_dirs()
    candidates = [
        DATA_ROOT / OAUTH_JSON_NAME,
        DATA_ROOT / "client_secret.json",
    ]
    for path in candidates:
        if not path.is_file():
            continue
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(raw, dict):
            cfg = _parse_oauth_dict(raw)
            if cfg:
                return cfg
    return None


def is_google_oauth_configured() -> bool:
    return load_google_oauth_config() is not None


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def make_pkce_pair() -> tuple[str, str]:
    verifier = _b64url(secrets.token_bytes(32))
    challenge = _b64url(hashlib.sha256(verifier.encode("ascii")).digest())
    return verifier, challenge


def make_oauth_state() -> str:
    return secrets.token_urlsafe(24)


def build_authorize_url(
    cfg: GoogleOAuthConfig,
    *,
    state: str,
    code_challenge: str,
) -> str:
    params = {
        "client_id": cfg.client_id,
        "redirect_uri": redirect_uri(),
        "response_type": "code",
        "scope": OAUTH_SCOPES,
        "state": state,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
        "access_type": "online",
        "prompt": "select_account",
    }
    return f"{cfg.auth_uri}?{urllib.parse.urlencode(params)}"


def _http_json(method: str, url: str, data: dict[str, str] | None = None) -> dict[str, Any]:
    body = None
    headers = {"Accept": "application/json"}
    if data is not None:
        body = urllib.parse.urlencode(data).encode("utf-8")
        headers["Content-Type"] = "application/x-www-form-urlencoded"
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            raw = resp.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:400]
        raise RuntimeError(f"google oauth http {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"google oauth network error: {exc}") from exc
    try:
        parsed = json.loads(raw) if raw else {}
    except json.JSONDecodeError as exc:
        raise RuntimeError("google oauth invalid json") from exc
    if not isinstance(parsed, dict):
        raise RuntimeError("google oauth unexpected payload")
    return parsed


def exchange_code(
    cfg: GoogleOAuthConfig,
    *,
    code: str,
    code_verifier: str,
) -> dict[str, Any]:
    return _http_json(
        "POST",
        cfg.token_uri,
        {
            "code": code,
            "client_id": cfg.client_id,
            "client_secret": cfg.client_secret,
            "redirect_uri": redirect_uri(),
            "grant_type": "authorization_code",
            "code_verifier": code_verifier,
        },
    )


def fetch_userinfo(access_token: str) -> dict[str, Any]:
    req = urllib.request.Request(
        GOOGLE_USERINFO_URI,
        headers={
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            raw = resp.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:400]
        raise RuntimeError(f"google userinfo http {exc.code}: {detail}") from exc
    parsed = json.loads(raw) if raw else {}
    if not isinstance(parsed, dict):
        raise RuntimeError("google userinfo unexpected payload")
    return parsed


def resolve_google_identity(token_payload: dict[str, Any]) -> tuple[str, str | None]:
    """Return (sub, email) from token response + userinfo if needed."""
    id_token = token_payload.get("id_token")
    access_token = token_payload.get("access_token")
    sub: str | None = None
    email: str | None = None

    if isinstance(id_token, str) and id_token.count(".") == 2:
        try:
            payload_b64 = id_token.split(".")[1]
            pad = "=" * (-len(payload_b64) % 4)
            claims = json.loads(base64.urlsafe_b64decode(payload_b64 + pad))
            if isinstance(claims, dict):
                sub = str(claims.get("sub") or "") or None
                email = str(claims.get("email") or "") or None
        except (ValueError, json.JSONDecodeError, OSError):
            pass

    if (not sub or not email) and isinstance(access_token, str) and access_token:
        info = fetch_userinfo(access_token)
        sub = sub or (str(info.get("sub") or "") or None)
        email = email or (str(info.get("email") or "") or None)

    if not sub:
        raise RuntimeError("google identity missing sub")
    return sub, email
