"""Post-process AI Deskline mark: punch black bg, sharp gradient bars, light/dark."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageFilter

ROOT = Path(__file__).resolve().parents[1]
IMG = ROOT / "web" / "static" / "img"
ANIM = IMG / "logo-anim"

# Prefer on-black AI (white D readable); fall back to light (dark D)
SRC_ON_BLACK = IMG / "ai-src-on-black.png"
SRC_LIGHT = IMG / "ai-src-light.png"

# Bar slots as fractions of glyph bbox (after trim) — tuned to AI composition
BARS_FRAC = [
    # left, top, width, height within letter bbox — then clamped inside hole
    (0.22, 0.58, 0.14, 0.28, (77, 179, 255), (10, 108, 240)),
    (0.40, 0.42, 0.14, 0.44, (62, 214, 196), (10, 155, 154)),
    (0.58, 0.28, 0.14, 0.58, (180, 236, 58), (95, 194, 24)),
]


def _is_colorful(r: int, g: int, b: int) -> bool:
    return (max(r, g, b) - min(r, g, b)) > 35 and max(r, g, b) > 50


def _flood_knockout_black(im: Image.Image, thr: int = 28) -> Image.Image:
    """Clear near-black background via flood from edges (keeps white D + bars)."""
    im = im.convert("RGBA")
    w, h = im.size
    px = im.load()
    assert px is not None
    visited = [[False] * w for _ in range(h)]
    stack: list[tuple[int, int]] = []

    def dark(x: int, y: int) -> bool:
        r, g, b, a = px[x, y]
        return a > 0 and r <= thr and g <= thr and b <= thr and not _is_colorful(r, g, b)

    for x in range(w):
        stack.append((x, 0))
        stack.append((x, h - 1))
    for y in range(h):
        stack.append((0, y))
        stack.append((w - 1, y))

    while stack:
        x, y = stack.pop()
        if x < 0 or y < 0 or x >= w or y >= h or visited[y][x]:
            continue
        visited[y][x] = True
        if not dark(x, y):
            continue
        px[x, y] = (0, 0, 0, 0)
        stack.extend(((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)))

    # Also clear remaining isolated near-black outside (anti-alias fringes stay on letter)
    for y in range(h):
        for x in range(w):
            r, g, b, a = px[x, y]
            if a > 0 and r <= 12 and g <= 12 and b <= 12 and not _is_colorful(r, g, b):
                px[x, y] = (0, 0, 0, 0)
    return im


def _flood_knockout_white(im: Image.Image, thr: int = 235) -> Image.Image:
    im = im.convert("RGBA")
    w, h = im.size
    px = im.load()
    assert px is not None
    visited = [[False] * w for _ in range(h)]
    stack: list[tuple[int, int]] = []

    def bright(x: int, y: int) -> bool:
        r, g, b, a = px[x, y]
        return a > 0 and r >= thr and g >= thr and b >= thr and not _is_colorful(r, g, b)

    for x in range(w):
        stack.append((x, 0))
        stack.append((x, h - 1))
    for y in range(h):
        stack.append((0, y))
        stack.append((w - 1, y))

    while stack:
        x, y = stack.pop()
        if x < 0 or y < 0 or x >= w or y >= h or visited[y][x]:
            continue
        visited[y][x] = True
        if not bright(x, y):
            continue
        px[x, y] = (255, 255, 255, 0)
        stack.extend(((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)))
    return im


def _erase_colorful(im: Image.Image) -> Image.Image:
    out = im.copy()
    px = out.load()
    assert px is not None
    for y in range(out.height):
        for x in range(out.width):
            r, g, b, a = px[x, y]
            if a > 8 and _is_colorful(r, g, b):
                px[x, y] = (0, 0, 0, 0)
    return out


def _glyph_bbox(im: Image.Image) -> tuple[int, int, int, int]:
    bbox = im.getbbox()
    if not bbox:
        raise RuntimeError("empty image after knockout")
    return bbox


def _paint_sharp_bars(im: Image.Image) -> Image.Image:
    out = im.copy()
    x0, y0, x1, y1 = _glyph_bbox(out)
    gw, gh = x1 - x0, y1 - y0
    for fx, fy, fw, fh, top, bot in BARS_FRAC:
        bx = x0 + int(fx * gw)
        by = y0 + int(fy * gh)
        bw = max(2, int(fw * gw))
        bh = max(2, int(fh * gh))
        bar = Image.new("RGBA", (bw, bh), (0, 0, 0, 0))
        bp = bar.load()
        assert bp is not None
        for yy in range(bh):
            t = yy / max(1, bh - 1)
            rgb = (
                int(top[0] + (bot[0] - top[0]) * t),
                int(top[1] + (bot[1] - top[1]) * t),
                int(top[2] + (bot[2] - top[2]) * t),
                255,
            )
            for xx in range(bw):
                bp[xx, yy] = rgb
        out.alpha_composite(bar, (bx, by))
    return out


def _recolor_letter(im: Image.Image, rgb: tuple[int, int, int]) -> Image.Image:
    out = im.copy()
    px = out.load()
    assert px is not None
    tr, tg, tb = rgb
    for y in range(out.height):
        for x in range(out.width):
            r, g, b, a = px[x, y]
            if a < 8 or _is_colorful(r, g, b):
                continue
            px[x, y] = (tr, tg, tb, a)
    return out


def _trim(im: Image.Image, pad: int = 28) -> Image.Image:
    bbox = im.getbbox()
    if not bbox:
        return im
    x0, y0, x1, y1 = bbox
    x0, y0 = max(0, x0 - pad), max(0, y0 - pad)
    x1, y1 = min(im.width, x1 + pad), min(im.height, y1 + pad)
    return im.crop((x0, y0, x1, y1))


def _fit(im: Image.Image, size: tuple[int, int]) -> Image.Image:
    canvas = Image.new("RGBA", size, (0, 0, 0, 0))
    scaled = im.copy()
    scaled.thumbnail((size[0] - 48, size[1] - 48), Image.Resampling.LANCZOS)
    x = (size[0] - scaled.width) // 2
    y = (size[1] - scaled.height) // 2
    canvas.alpha_composite(scaled, (x, y))
    return canvas


def build_dark() -> Image.Image:
    src = Image.open(SRC_ON_BLACK).convert("RGBA")
    # 2× then process for softer final downsample
    src = src.resize((src.width * 2, src.height * 2), Image.Resampling.LANCZOS)
    im = _flood_knockout_black(src)
    im = _erase_colorful(im)
    im = _paint_sharp_bars(im)
    im = _recolor_letter(im, (244, 247, 245))
    a = im.getchannel("A").filter(ImageFilter.GaussianBlur(0.35))
    r, g, b, _ = im.split()
    im = Image.merge("RGBA", (r, g, b, a))
    return _trim(im)


def build_light(dark: Image.Image) -> Image.Image:
    # Same silhouette as dark; navy letter for light theme
    return _recolor_letter(dark.copy(), (25, 34, 50))


def main() -> None:
    if not SRC_ON_BLACK.exists():
        raise SystemExit(f"missing {SRC_ON_BLACK} — copy AI asset first")
    ANIM.mkdir(exist_ok=True)
    dark = build_dark()
    light = build_light(dark)

    _fit(light, (664, 761)).save(IMG / "logo.png", optimize=True)
    _fit(dark, (664, 761)).save(IMG / "logo-dark.png", optimize=True)
    _fit(light, (1328, 1522)).save(ANIM / "logo-splash.png", optimize=True)
    _fit(dark, (1328, 1522)).save(ANIM / "logo-splash-dark.png", optimize=True)

    d = Image.open(IMG / "logo-dark.png")
    print(
        "ok",
        "corner_a",
        d.getpixel((0, 0))[3],
        "mid",
        d.getpixel((d.width // 2, d.height // 2)),
    )


if __name__ == "__main__":
    main()
