"""Post-restart health check for Deskline summary grouping/favicons."""
from __future__ import annotations

import sys
from pathlib import Path

install_root = Path(sys.argv[1]) if len(sys.argv) > 1 else None
if install_root:
    sys.path.insert(0, str(install_root))

from deskline import __version__
from deskline.config import DB_PATH
from deskline.db import Database


def main() -> int:
    print("version", __version__)
    if not __version__.startswith("0.4."):
        print("unexpected version", __version__, file=sys.stderr)
        return 1
    db = Database(DB_PATH)
    summary = db.summary_for_day()
    names = [a["name"] for a in summary["by_activity"]]
    bad = [
        n
        for n in names
        if "новых сообщен" in n.lower() or "новое сообщен" in n.lower()
    ]
    if bad:
        print("messenger still fragmented:", bad, file=sys.stderr)
        return 1
    messenger = [a for a in summary["by_activity"] if a["name"] == "Яндекс Мессенджер"]
    print(
        "messenger_rows",
        len(messenger),
        "sec",
        messenger[0]["sec"] if messenger else 0,
    )
    habr = [a for a in summary["by_activity"] if a["name"] == "Habr"]
    if habr:
        icon = habr[0].get("icon_url") or ""
        print("habr_icon", icon)
        if not icon.startswith("/media/icons/site_"):
            print("habr icon not site favicon:", icon, file=sys.stderr)
            return 1
    print("OK summary healthy")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
