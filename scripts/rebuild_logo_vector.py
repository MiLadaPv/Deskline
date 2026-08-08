"""Build crisp Deskline mark: smooth D + sharp bars clipped to the D counter (stencil)."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
IMG = ROOT / "web" / "static" / "img"
PARTIAL = ROOT / "web" / "templates" / "partials" / "boot_logo.html"

# Bars sit fully inside the D counter (hole left edge ~248). Sharp corners.
BARS = [
    (270, 468, 68, 132, "g1", "#4DB3FF", "#0A6CF0"),
    (352, 378, 70, 222, "g2", "#3ED6C4", "#0A9B9A"),
    (436, 300, 70, 300, "g3", "#B4EC3A", "#5FC218"),
]

# Outer + hole (evenodd). Hole alone is used as clipPath for stencil bars.
D_OUTER = (
    "M170 50 "
    "C170 42 176 36 186 36 "
    "H310 "
    "C482 36 606 170 606 380 "
    "C606 590 482 725 310 725 "
    "H186 "
    "C176 725 170 718 170 710 "
    "V640 "
    "C126 632 90 590 90 538 "
    "V212 "
    "C90 160 126 118 170 110 "
    "V50 "
    "Z"
)

D_HOLE = (
    "M248 154 "
    "H312 "
    "C432 154 500 242 500 380 "
    "C500 518 432 608 312 608 "
    "H248 "
    "V154 "
    "Z"
)

D_PATH = f"{D_OUTER} {D_HOLE}"


def _grads_and_bars(prefix: str, animate: bool) -> tuple[str, str]:
    grads: list[str] = []
    body: list[str] = []
    for i, (x, y, w, h, gid, c0, c1) in enumerate(BARS, 1):
        uid = f"{prefix}{gid}"
        grads.append(
            f'    <linearGradient id="{uid}" x1="{x + w / 2:.1f}" y1="{y}" '
            f'x2="{x + w / 2:.1f}" y2="{y + h}" gradientUnits="userSpaceOnUse">'
            f'<stop offset="0%" stop-color="{c0}"/>'
            f'<stop offset="100%" stop-color="{c1}"/>'
            f"</linearGradient>"
        )
        rect = (
            f'<rect class="logo-bar logo-bar-{i}" x="{x}" y="{y}" '
            f'width="{w}" height="{h}" rx="0" ry="0" fill="url(#{uid})"/>'
        )
        if animate:
            cx, by = x + w / 2, y + h
            begin = {1: "0.10s", 2: "0.20s", 3: "0.30s"}[i]
            body.append(
                f'<g class="logo-bar-grow" style="--bar-delay:{begin}">'
                f'<g transform="translate({cx} {by})">'
                f'<g class="logo-bar-scale">'
                f'<g transform="translate({-cx} {-by})">{rect}</g>'
                f"</g></g></g>"
            )
        else:
            body.append(rect)
    return "\n".join(grads), "\n".join(body)


def build_svg(fill: str, prefix: str, animate: bool = False, for_inline: bool = False) -> str:
    grads, bars = _grads_and_bars(prefix, animate)
    clip_id = f"{prefix}hole"
    open_tag = (
        f'<svg class="boot-logo-svg" viewBox="0 0 664 761" fill="none" '
        f'shape-rendering="geometricPrecision" aria-hidden="true" '
        f'xmlns="http://www.w3.org/2000/svg">'
    )
    # Stencil: bars under clip of counter, then D on top so the stem masks edges.
    inner = (
        f"{open_tag}\n"
        f"  <defs>\n{grads}\n"
        f'    <clipPath id="{clip_id}"><path d="{D_HOLE}"/></clipPath>\n'
        f"  </defs>\n"
        f'  <g class="logo-bars" clip-path="url(#{clip_id})">\n'
        f"    {bars}\n"
        f"  </g>\n"
        f'  <path class="logo-d" fill="{fill}" fill-rule="evenodd" d="{D_PATH}"/>\n'
        f"</svg>"
    )
    if for_inline:
        return inner
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + inner + "\n"


def build_partial() -> str:
    light = build_svg("#192232", "bl-", animate=True, for_inline=True)
    dark = build_svg("#F4F7F5", "bd-", animate=True, for_inline=True)
    return (
        "{# Inline splash mark — stencil bars inside D counter #}\n"
        f'<div class="boot-logo-anim boot-logo-anim-light">{light}</div>\n'
        f'<div class="boot-logo-anim boot-logo-anim-dark">{dark}</div>\n'
    )


def main() -> None:
    (IMG / "logo.svg").write_text(build_svg("#192232", "lg-"), encoding="utf-8")
    (IMG / "logo-dark.svg").write_text(build_svg("#F4F7F5", "dg-"), encoding="utf-8")
    (IMG / "logo-splash.svg").write_text(build_svg("#192232", "ls-", animate=True), encoding="utf-8")
    (IMG / "logo-splash-dark.svg").write_text(
        build_svg("#F4F7F5", "lsd-", animate=True), encoding="utf-8"
    )
    PARTIAL.write_text(build_partial(), encoding="utf-8")
    print("wrote SVGs +", PARTIAL.relative_to(ROOT))


if __name__ == "__main__":
    main()
