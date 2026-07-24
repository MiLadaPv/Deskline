"""Logo gallery catalog for /logos."""

from __future__ import annotations

import re
from pathlib import Path

from deskline.config import WEB_ROOT

LOGOS_DIR = WEB_ROOT / "static" / "img" / "logos"

# Display order + copy (id must match filename stem)
LOGO_META: list[dict[str, str | bool]] = [
    {
        "id": "01-pulse-d",
        "title": "01 · Pulse D",
        "blurb": "D + линия дня с пиком фокуса. Самый «продуктовый» смысл.",
    },
    {
        "id": "02-ribbon",
        "title": "02 · Day Ribbon",
        "blurb": "Абстрактная лента дня без буквы — спокойная иконка.",
    },
    {
        "id": "03-negative-d",
        "title": "03 · Negative D",
        "blurb": "Смелый solid-знак. Хорошо читается в трее и на ярлыке.",
    },
    {
        "id": "04-gauge",
        "title": "04 · Focus Gauge",
        "blurb": "Кольцо фокуса + намёк на D. Связь с диаграммами в UI.",
    },
    {
        "id": "05-layers",
        "title": "05 · Desk Layers",
        "blurb": "Слои стола и пик. Тихий, «wellness» характер.",
    },
    {
        "id": "06-stroke-dl",
        "title": "06 · Stroke DL",
        "blurb": "Один жест: D переходит в L. Геометрия бренда.",
    },
    {
        "id": "07-window",
        "title": "07 · Focus Window",
        "blurb": "Окно рабочего дня + sparkline. Понятнее новичкам.",
    },
    {
        "id": "08-classic-solid",
        "title": "08 · Classic Solid",
        "blurb": "Pulse D на зелёном поле. Кандидат в app icon / favicon.",
    },
    {
        "id": "09-hex-slash",
        "title": "09 · Hex Slash",
        "blurb": "Современный tech-знак. Меньше «трекер», больше бренд.",
    },
    {
        "id": "10-split-dayline",
        "title": "10 · Split Dayline",
        "blurb": "Диагональный split + timeline. Самый характерный силуэт.",
    },
    {
        "id": "11-sunrise",
        "title": "11 · Sunrise Desk",
        "blurb": "Рассвет над линией стола. Тёплый, человечный.",
    },
    {
        "id": "13-soft-seal",
        "title": "13 · Soft Seal",
        "blurb": "Печать / badge. Хорош для splash и onboarding.",
    },
    {
        "id": "14-dual-peak",
        "title": "14 · Dual Peak",
        "blurb": "График фокуса как логотип. Чистая метафора продукта.",
    },
    {
        "id": "12-lockup",
        "title": "12 · Wordmark Lockup",
        "blurb": "Иконка + Deskline для сайта, установщика и шапки.",
        "wide": True,
    },
]


def _unique_svg_ids(svg: str, prefix: str) -> str:
    """Prefix url(#id) / id=\"...\" so many inlined SVGs don't clash."""
    ids = set(re.findall(r'\bid="([^"]+)"', svg))
    out = svg
    for raw in ids:
        safe = f"{prefix}-{raw}"
        out = out.replace(f'id="{raw}"', f'id="{safe}"')
        out = out.replace(f"url(#{raw})", f"url(#{safe})")
    return out


def load_logo_cards() -> list[dict]:
    cards: list[dict] = []
    for meta in LOGO_META:
        lid = str(meta["id"])
        path = LOGOS_DIR / f"{lid}.svg"
        if not path.is_file():
            continue
        try:
            raw = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            raw = path.read_text(encoding="cp1252")
        raw = raw.replace("\u00b7", "-").replace("·", "-")
        # Strip XML declaration if present
        raw = re.sub(r"<\?xml[^>]*\?>\s*", "", raw)
        svg = _unique_svg_ids(raw, lid.replace("-", ""))
        cards.append(
            {
                "id": lid,
                "title": meta["title"],
                "blurb": meta["blurb"],
                "wide": bool(meta.get("wide")),
                "svg": svg,
            }
        )
    return cards
