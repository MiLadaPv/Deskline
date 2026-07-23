from __future__ import annotations

import hashlib
import secrets


def new_ingest_token() -> str:
    return secrets.token_urlsafe(24)


def hash_ingest_token(token: str) -> str:
    return hashlib.sha256(token.strip().encode("utf-8")).hexdigest()


def initials_from_name(name: str) -> str:
    parts = [p for p in str(name or "").strip().split() if p]
    if not parts:
        return "?"
    if len(parts) == 1:
        return parts[0][:2].upper()
    return (parts[0][0] + parts[1][0]).upper()


EMPLOYEE_COLORS = (
    "#1f6b56",
    "#2a6f9e",
    "#8b5a2b",
    "#6b3fa0",
    "#b45309",
    "#0f766e",
    "#be123c",
    "#365314",
)
