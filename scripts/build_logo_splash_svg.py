"""Build crisp SVG splash logos with SMIL bar-grow animation (true transparency)."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
IMG = ROOT / "web" / "static" / "img"

BARS = [
    (1, 155.0, 498.0, 85.0, 146.0, "0.12s"),
    (2, 252.0, 407.0, 86.0, 236.0, "0.22s"),
    (3, 352.0, 309.0, 86.0, 320.0, "0.32s"),
]

STYLE = """  <style>
    .logo-d { opacity: 0; animation: d-in 0.35s ease 0.05s forwards; }
    .logo-bar {
      transform-box: fill-box;
      transform-origin: center bottom;
      animation: bar-grow 0.85s cubic-bezier(0.22, 1, 0.36, 1) forwards;
    }
    .logo-bar-1 { transform: scaleY(0); animation-delay: 0.12s; }
    .logo-bar-2 { transform: scaleY(0); animation-delay: 0.22s; }
    .logo-bar-3 { transform: scaleY(0); animation-delay: 0.32s; }
    @keyframes d-in { to { opacity: 1; } }
    @keyframes bar-grow { from { transform: scaleY(0); } to { transform: scaleY(1); } }
  </style>
"""


def _wrap_bar(svg: str, n: int, x: float, y: float, w: float, h: float, begin: str) -> str:
    cx = x + w / 2
    by = y + h
    pat = rf'(<rect class="logo-bar logo-bar-{n}"[^/]*/>)'
    m = re.search(pat, svg)
    if not m:
        raise RuntimeError(f"bar {n} not found")
    rect = m.group(1)
    smil = (
        f'<animateTransform attributeName="transform" type="scale" '
        f'dur="0.85s" begin="{begin}" fill="freeze" from="1 0" to="1 1" '
        f'calcMode="spline" keySplines="0.22 1 0.36 1" keyTimes="0;1"/>'
    )
    wrapped = (
        f'<g transform="translate({cx} {by})">'
        f'<g transform="scale(1 0)">'
        f"{smil}"
        f'<g transform="translate({-cx} {-by})">{rect}</g>'
        f"</g></g>"
    )
    return svg[: m.start()] + wrapped + svg[m.end() :]


def build(src_name: str, out_name: str, id_prefix: str) -> None:
    text = (IMG / src_name).read_text(encoding="utf-8")
    for gid in ("g1", "g2", "g3"):
        text = text.replace(f'id="{gid}"', f'id="{id_prefix}{gid}"')
        text = text.replace(f"url(#{gid})", f"url(#{id_prefix}{gid})")
    needle = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 664 761" '
        'fill="none" aria-hidden="true">'
    )
    if needle not in text:
        raise RuntimeError(f"unexpected svg header in {src_name}")
    text = text.replace(needle, needle + "\n" + STYLE, 1)
    for n, x, y, w, h, begin in BARS:
        text = _wrap_bar(text, n, x, y, w, h, begin)
    out = IMG / out_name
    out.write_text(text, encoding="utf-8")
    print("ok", out.name, out.stat().st_size)


def main() -> None:
    build("logo.svg", "logo-splash.svg", "ls-")
    build("logo-dark.svg", "logo-splash-dark.svg", "lsd-")


if __name__ == "__main__":
    main()
