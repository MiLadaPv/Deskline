"""Lemon Squeezy license activation + offline cache."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Any

from deskline.license_store import clear_license, load_license, save_license

LS_ACTIVATE_URL = "https://api.lemonsqueezy.com/v1/licenses/activate"
LS_VALIDATE_URL = "https://api.lemonsqueezy.com/v1/licenses/validate"

# Local/dev keys when DESKLINE_LICENSE_DEV=1 or no API key configured.
DEV_KEYS = {
    "DESKLINE-PRO-DEV": {"tier": "pro", "expires_at": None},
    "DESKLINE-PRO-LIFE-DEV": {"tier": "pro", "expires_at": None},
    "DESKLINE-TEAM-DEV": {"tier": "team", "expires_at": None},
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _dev_mode() -> bool:
    if os.environ.get("DESKLINE_LICENSE_DEV", "").strip() in {"1", "true", "yes"}:
        return True
    # Allow deterministic tests / offline demos without LS credentials.
    return not bool(os.environ.get("DESKLINE_LEMON_API_KEY", "").strip())


def normalize_key(key: str) -> str:
    return "-".join(part for part in key.strip().upper().replace(" ", "").split("-") if part)


def activate_license(key: str, *, instance_name: str = "Deskline PC") -> dict[str, Any]:
    """Activate a license key; persists signed cache on success."""
    norm = normalize_key(key)
    if not norm:
        raise ValueError("Введите лицензионный ключ")

    if norm in DEV_KEYS and _dev_mode():
        meta = DEV_KEYS[norm]
        payload = {
            "key": norm,
            "tier": meta["tier"],
            "status": "active",
            "expires_at": meta["expires_at"],
            "last_validated_at": _now_iso(),
            "instance_name": instance_name,
            "source": "dev",
        }
        save_license(payload)
        return payload

    api_key = os.environ.get("DESKLINE_LEMON_API_KEY", "").strip()
    if not api_key:
        raise ValueError(
            "Оплата ещё не подключена на этом билде. "
            "Задайте DESKLINE_LEMON_API_KEY или используйте пробный период."
        )

    body = json.dumps({"license_key": norm, "instance_name": instance_name}).encode("utf-8")
    req = urllib.request.Request(
        LS_ACTIVATE_URL,
        data=body,
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise ValueError(f"Lemon Squeezy отклонил ключ ({exc.code}): {detail[:240]}") from exc
    except urllib.error.URLError as exc:
        raise ValueError(f"Нет сети для активации: {exc.reason}") from exc

    meta = data.get("meta") if isinstance(data, dict) else None
    lic = data.get("license_key") if isinstance(data, dict) else None
    if not isinstance(meta, dict):
        meta = {}
    if not isinstance(lic, dict):
        lic = {}

    if not meta.get("valid", False) and str(lic.get("status") or "").lower() != "active":
        raise ValueError(str(meta.get("error") or "Ключ недействителен"))

    variant = str(meta.get("variant_name") or lic.get("product_name") or "pro").lower()
    tier = "team" if "team" in variant else "pro"
    expires = lic.get("expires_at")
    payload = {
        "key": norm,
        "tier": tier,
        "status": "active",
        "expires_at": expires,
        "last_validated_at": _now_iso(),
        "instance_id": meta.get("instance_id"),
        "instance_name": instance_name,
        "source": "lemonsqueezy",
        "customer_email": (meta.get("customer_email") or None),
    }
    # Never persist raw email if empty; redact storage of PII beyond necessity —
    # keep only for support correlation when LS returns it.
    if not payload["customer_email"]:
        payload.pop("customer_email", None)
    save_license(payload)
    return {k: v for k, v in payload.items() if k != "customer_email"}


def deactivate_local() -> None:
    clear_license()


def touch_validated(payload: dict[str, Any] | None = None) -> dict[str, Any] | None:
    """Refresh last_validated_at for offline grace (e.g. after successful validate)."""
    data = payload or load_license()
    if not data:
        return None
    data = dict(data)
    data["last_validated_at"] = _now_iso()
    data["status"] = "active"
    save_license(data)
    return data


def current_license() -> dict[str, Any] | None:
    return load_license()
