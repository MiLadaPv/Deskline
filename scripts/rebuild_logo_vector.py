"""Build a crisp geometric Deskline mark (smooth cubics, exact bar slots)."""

from __future__ import annotations

import re
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
IMG = ROOT / "web" / "static" / "img"

BARS = [
    (155, 498, 85, 146, 42.5, "g1", "#4DB3FF", "#0A6CF0"),
    (252, 407, 86, 236, 43.0, "g2", "#3ED6C4", "#0A9B9A"),
    (352, 309, 86, 320, 43.0, "g3", "#B4EC3A", "#5FC218"),
]

# Smooth bold D matched to official 664×761 artboard + bar slots.
# Outer + inner hole (evenodd). Pure cubics — no traced polylines.
D_PATH = (
    "M168 48 "
    "C168 40 174 36 184 36 "
    "H312 "
    "C478 36 604 168 604 380 "
    "C604 592 478 725 312 725 "
    "H184 "
    "C174 725 168 720 168 712 "
    "V638 "
    "C128 630 92 590 92 540 "
    "V210 "
    "C92 160 128 120 168 112 "
    "V48 "
    "Z "
    "M248 152 "
    "H314 "
    "C430 152 498 240 498 380 "
    "C498 520 430 610 314 610 "
    "H248 "
    "V152 "
    "Z"
)


def build_svg(fill: str, prefix: str, animate: bool = False) -> str:
    grads: list[str] = []
    body: list[str] = []
    style = ""
    if animate:
        style = """  <style>
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
    for i, (x, y, w, h, rx, gid, c0, c1) in enumerate(BARS, 1):
        uid = f"{prefix}{gid}"
        grads.append(
            f'    <linearGradient id="{uid}" x1="{x + w / 2:.1f}" y1="{y}" '
            f'x2="{x + w / 2:.1f}" y2="{y + h}" gradientUnits="userSpaceOnUse">\n'
            f'      <stop offset="0%" stop-color="{c0}"/>\n'
            f'      <stop offset="100%" stop-color="{c1}"/>\n'
            f"    </linearGradient>"
        )
        rect = (
            f'<rect class="logo-bar logo-bar-{i}" x="{x}" y="{y}" '
            f'width="{w}" height="{h}" rx="{rx}" fill="url(#{uid})"/>'
        )
        if animate:
            cx, by = x + w / 2, y + h
            begin = {1: "0.12s", 2: "0.22s", 3: "0.32s"}[i]
            smil = (
                f'<animateTransform attributeName="transform" type="scale" '
                f'dur="0.85s" begin="{begin}" fill="freeze" from="1 0" to="1 1" '
                f'calcMode="spline" keySplines="0.22 1 0.36 1" keyTimes="0;1"/>'
            )
            body.append(
                f'  <g transform="translate({cx} {by})">'
                f'<g transform="scale(1 0)">{smil}'
                f'<g transform="translate({-cx} {-by})">{rect}</g></g></g>'
            )
        else:
            body.append(f"  {rect}")

    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 664 761" '
        'fill="none" shape-rendering="geometricPrecision" aria-hidden="true">\n'
        f"{style}"
        "  <defs>\n"
        + "\n".join(grads)
        + "\n  </defs>\n"
        f'  <path class="logo-d" fill="{fill}" fill-rule="evenodd" d="{D_PATH}"/>\n'
        + "\n".join(body)
        + "\n</svg>\n"
    )


def render_png(svg_path: Path, out: Path) -> None:
    chrome = Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe")
    if not chrome.exists():
        chrome = Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe")
    svg = svg_path.read_text(encoding="utf-8")
    svg = re.sub(r"<\?xml[^>]*>", "", svg)
    html = (
        "<!doctype html><html><body style='margin:0;background:transparent'>"
        f"{svg}</body></html>"
    )
    html_path = ROOT / "scripts/_render_logo.html"
    html_path.write_text(html, encoding="utf-8")
    url = "file:///" + str(html_path).replace("\\", "/")
    tmp = out.with_suffix(".shot.png")
    subprocess.run(
        [
            str(chrome),
            "--headless=new",
            "--disable-gpu",
            "--default-background-color=0",
            "--window-size=664,761",
            f"--screenshot={tmp}",
            url,
        ],
        check=False,
    )
    time.sleep(1.2)
    from PIL import Image

    im = Image.open(tmp).convert("RGBA")
    # Chrome screenshot may include window chrome; crop to content if needed
    if im.size != (664, 761):
        # center-crop / resize
        im = im.resize((664, 761), Image.Resampling.LANCZOS)
    im.save(out)
    print("wrote", out.name, "corner", im.getpixel((0, 0)))


def main() -> None:
    (IMG / "logo.svg").write_text(build_svg("#192232", "lg-"), encoding="utf-8")
    (IMG / "logo-dark.svg").write_text(build_svg("#F4F7F5", "dg-"), encoding="utf-8")
    (IMG / "logo-splash.svg").write_text(build_svg("#192232", "ls-", True), encoding="utf-8")
    (IMG / "logo-splash-dark.svg").write_text(build_svg("#F4F7F5", "lsd-", True), encoding="utf-8")
    print("wrote geometric SVGs")
    render_png(IMG / "logo.svg", IMG / "logo.png")
    render_png(IMG / "logo-dark.svg", IMG / "logo-dark.png")


if __name__ == "__main__":
    main()
