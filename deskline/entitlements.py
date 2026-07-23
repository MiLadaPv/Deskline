"""License + freemium entitlements for Deskline Free / Pro / Team."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Any

FREE_HISTORY_DAYS = 14
FREE_MAX_PROJECTS = 3
TRIAL_DAYS = 14
OFFLINE_GRACE_DAYS = 14

TIER_FREE = "free"
TIER_TRIAL = "trial"
TIER_PRO = "pro"
TIER_TEAM = "team"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_iso(value: str | None) -> datetime | None:
    if not value or not isinstance(value, str):
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


@dataclass(frozen=True)
class Entitlements:
    tier: str
    label: str
    is_pro: bool
    is_team: bool
    history_days: int | None  # None = unlimited
    max_projects: int | None  # None = unlimited
    screenshots: bool
    export: bool
    company_hub: bool
    trial_ends_at: str | None
    license_key_masked: str | None
    status_detail: str

    def oldest_allowed_day(self, today: date | None = None) -> date | None:
        if self.history_days is None:
            return None
        day = today or date.today()
        return day - timedelta(days=self.history_days - 1)

    def day_allowed(self, day: date, today: date | None = None) -> bool:
        oldest = self.oldest_allowed_day(today)
        if oldest is None:
            return True
        return day >= oldest


def ensure_first_run(cfg: dict[str, Any]) -> dict[str, Any]:
    """Stamp first_run_at once; returns config (caller should save if changed)."""
    if cfg.get("first_run_at"):
        return cfg
    cfg = dict(cfg)
    cfg["first_run_at"] = _now().isoformat()
    return cfg


def trial_active(cfg: dict[str, Any], now: datetime | None = None) -> tuple[bool, datetime | None]:
    first = _parse_iso(str(cfg.get("first_run_at") or "") or None)
    if not first:
        return False, None
    now = now or _now()
    ends = first + timedelta(days=TRIAL_DAYS)
    return now < ends, ends


def resolve_entitlements(
    cfg: dict[str, Any],
    license_payload: dict[str, Any] | None,
    *,
    now: datetime | None = None,
) -> Entitlements:
    """Resolve effective tier from license file + trial clock."""
    now = now or _now()
    lic = license_payload or {}
    tier = str(lic.get("tier") or "").lower().strip()
    status = str(lic.get("status") or "inactive").lower()
    expires = _parse_iso(str(lic.get("expires_at") or "") or None)
    last_check = _parse_iso(str(lic.get("last_validated_at") or "") or None)
    key = str(lic.get("key") or "")
    masked = _mask_key(key) if key else None

    offline_ok = True
    if last_check is not None:
        offline_ok = now <= last_check + timedelta(days=OFFLINE_GRACE_DAYS)

    license_ok = status in {"active", "inactive_grace"} and offline_ok
    if expires is not None and now >= expires:
        license_ok = False

    if license_ok and tier == TIER_TEAM:
        return Entitlements(
            tier=TIER_TEAM,
            label="Team",
            is_pro=True,
            is_team=True,
            history_days=None,
            max_projects=None,
            screenshots=True,
            export=True,
            company_hub=True,
            trial_ends_at=None,
            license_key_masked=masked,
            status_detail="Team license active",
        )

    if license_ok and tier in {TIER_PRO, "lifetime"}:
        return Entitlements(
            tier=TIER_PRO,
            label="Pro",
            is_pro=True,
            is_team=False,
            history_days=None,
            max_projects=None,
            screenshots=True,
            export=True,
            company_hub=False,
            trial_ends_at=None,
            license_key_masked=masked,
            status_detail="Pro license active",
        )

    active, ends = trial_active(cfg, now=now)
    if active and ends is not None:
        return Entitlements(
            tier=TIER_TRIAL,
            label="Pro trial",
            is_pro=True,
            is_team=False,
            history_days=None,
            max_projects=None,
            screenshots=True,
            export=True,
            company_hub=False,
            trial_ends_at=ends.isoformat(),
            license_key_masked=masked,
            status_detail=f"Trial until {ends.date().isoformat()}",
        )

    detail = "Free plan"
    if key and not license_ok:
        detail = "License expired or needs revalidation — Free limits apply"
    return Entitlements(
        tier=TIER_FREE,
        label="Free",
        is_pro=False,
        is_team=False,
        history_days=FREE_HISTORY_DAYS,
        max_projects=FREE_MAX_PROJECTS,
        screenshots=False,
        export=False,
        company_hub=False,
        trial_ends_at=None,
        license_key_masked=masked,
        status_detail=detail,
    )


def entitlements_public_dict(ent: Entitlements) -> dict[str, Any]:
    return {
        "tier": ent.tier,
        "label": ent.label,
        "is_pro": ent.is_pro,
        "is_team": ent.is_team,
        "history_days": ent.history_days,
        "max_projects": ent.max_projects,
        "screenshots": ent.screenshots,
        "export": ent.export,
        "company_hub": ent.company_hub,
        "trial_ends_at": ent.trial_ends_at,
        "license_key_masked": ent.license_key_masked,
        "status_detail": ent.status_detail,
        "checkout": checkout_urls(),
    }


def checkout_urls() -> dict[str, str]:
    import os

    return {
        "annual": os.environ.get(
            "DESKLINE_CHECKOUT_URL_ANNUAL",
            "https://andalusgames.lemonsqueezy.com/checkout/buy/deskline-pro-annual",
        ),
        "lifetime": os.environ.get(
            "DESKLINE_CHECKOUT_URL_LIFETIME",
            "https://andalusgames.lemonsqueezy.com/checkout/buy/deskline-pro-lifetime",
        ),
        "pricing_page": "/welcome#pricing",
    }


def _mask_key(key: str) -> str:
    raw = "".join(ch for ch in key.upper() if ch.isalnum() or ch == "-")
    if len(raw) <= 8:
        return "••••"
    return f"{raw[:4]}…{raw[-4:]}"
