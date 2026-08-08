"""Build crisp Deskline mark: wider D + bright bars clipped flush to the counter."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
IMG = ROOT / "web" / "static" / "img"
PARTIAL = ROOT / "web" / "templates" / "partials" / "boot_logo.html"

# Hole bottom = 608, left = 232. Bars extend slightly past edges so clipPath
# cuts them flush to the D counter (no visible gap).
BAR_BOTTOM = 612  # 4px past hole floor → stencil edge sits on the letter
BARS = [
    # x, y, w, h, gid, bright_top, rich_bottom
    (232, BAR_BOTTOM - 148, 82, 148, "g1", "#B8E4FF", "#1A8CFF"),
    (328, BAR_BOTTOM - 248, 84, 248, "g2", "#7FF5E0", "#10D4B0"),
    (426, BAR_BOTTOM - 336, 96, 336, "g3", "#ECFF6B", "#8AE010"),
]

# Wider D: thicker overall glyph, roomy counter, clean vertical left stem.
D_OUTER = (
    "M95 56 "
    "C95 44 108 36 124 36 "
    "H330 "
    "C520 36 640 170 640 380 "
    "C640 590 520 725 330 725 "
    "H124 "
    "C108 725 95 716 95 704 "
    "V56 "
    "Z"
)

D_HOLE = (
    "M232 154 "
    "H310 "
    "C450 154 530 242 530 380 "
    "C530 518 450 608 310 608 "
    "H232 "
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
            f'<stop offset="45%" stop-color="{c0}"/>'
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
        "{# Inline splash mark — wider D, bright flush bars #}\n"
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
