"""Optional Google OAuth (OIDC) unlock for local Deskline."""

from __future__ import annotations

import base64
import hashlib
import json
import os
import secrets
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any

from deskline.config import BASE_URL, DATA_ROOT, ensure_data_dirs

GOOGLE_AUTH_URI = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URI = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URI = "https://openidconnect.googleapis.com/v1/userinfo"
OAUTH_SCOPES = "openid email profile"
OAUTH_STATE_COOKIE = "deskline_oauth"
OAUTH_JSON_NAME = "google-oauth.json"
REDIRECT_PATH = "/api/auth/google/callback"


@dataclass(frozen=True)
class GoogleOAuthConfig:
    client_id: str
    client_secret: str
    token_uri: str = GOOGLE_TOKEN_URI
    auth_uri: str = GOOGLE_AUTH_URI


def redirect_uri() -> str:
    return f"{BASE_URL.rstrip('/')}{REDIRECT_PATH}"


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
