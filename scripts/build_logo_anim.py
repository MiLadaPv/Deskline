"""Build crisp Deskline logo layers + bar-grow animation from official SVG."""

from __future__ import annotations

import re
from pathlib import Path

from PIL import Image, ImageDraw
from reportlab.graphics import renderPM
from svglib.svglib import svg2rlg

ROOT = Path(__file__).resolve().parents[1]
IMG = ROOT / "web" / "static" / "img"
OUT = IMG / "logo-anim"
SRC_SVG = IMG / "logo.svg"

# 664×761 × 3 — crisp for Jitter / splash.
SCALE = 3

BARS = [
    {
        "id": 1,
        "x": 155,
        "y": 498,
        "w": 85,
        "h": 146,
        "rx": 42.5,
        "g": ("#4DB3FF", "#0A6CF0"),
    },
    {
        "id": 2,
        "x": 252,
        "y": 407,
        "w": 86,
        "h": 236,
        "rx": 43.0,
        "g": ("#3ED6C4", "#0A9B9A"),
    },
    {
        "id": 3,
        "x": 352,
        "y": 309,
        "w": 86,
        "h": 320,
        "rx": 43.0,
        "g": ("#B4EC3A", "#5FC218"),
    },
]


def _hex_to_rgb(value: str) -> tuple[int, int, int]:
    v = value.lstrip("#")
    return int(v[0:2], 16), int(v[2:4], 16), int(v[4:6], 16)


def _extract_d_path(svg_text: str) -> str:
    m = re.search(r'<path class="logo-d"[^>]*\sd="([^"]+)"', svg_text)
    if not m:
        raise RuntimeError("logo-d path not found in SVG")
    return m.group(1)


def _svg_doc(body: str) -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 664 761" '
        'width="664" height="761" fill="none">\n'
        f"{body}\n"
        "</svg>\n"
    )


def write_layer_svgs(d_fill: str, prefix: str) -> Path:
    """Write vector layers for Jitter (infinite sharpness)."""
    d_path = _extract_d_path(SRC_SVG.read_text(encoding="utf-8"))
    d_svg = OUT / f"{prefix}layer-d.svg"
    d_svg.write_text(
        _svg_doc(f'  <path fill="{d_fill}" fill-rule="evenodd" d="{d_path}"/>'),
        encoding="utf-8",
    )
    for bar in BARS:
        top, bot = bar["g"]
        body = f"""  <defs>
    <linearGradient id="g" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="{top}"/>
      <stop offset="100%" stop-color="{bot}"/>
    </linearGradient>
  </defs>
  <rect x="{bar['x']}" y="{bar['y']}" width="{bar['w']}" height="{bar['h']}" rx="{bar['rx']}" fill="url(#g)"/>"""
        (OUT / f"{prefix}layer-bar-{bar['id']}.svg").write_text(_svg_doc(body), encoding="utf-8")
    return d_svg


def render_d_png(svg_path: Path, png_path: Path, scale: int = SCALE) -> Image.Image:
    drawing = svg2rlg(str(svg_path))
    if drawing is None:
        raise RuntimeError(f"failed to parse {svg_path}")
    drawing.width *= scale
    drawing.height *= scale
    drawing.scale(scale, scale)
    renderPM.drawToFile(drawing, str(png_path), fmt="PNG", dpi=72)
    return Image.open(png_path).convert("RGBA")


def draw_bar_layer(canvas_w: int, canvas_h: int, bar: dict, scale: int = SCALE) -> Image.Image:
    """Antialiased rounded bar with vertical gradient (supersampled)."""
    ss = 2  # supersample then downscale
    W, H = canvas_w * ss, canvas_h * ss
    s = scale * ss
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    x = int(round(bar["x"] * s))
    y = int(round(bar["y"] * s))
    w = int(round(bar["w"] * s))
    h = int(round(bar["h"] * s))
    rx = int(round(min(bar["rx"] * s, w / 2, h / 2)))

    # Gradient strip
    top = _hex_to_rgb(bar["g"][0])
    bot = _hex_to_rgb(bar["g"][1])
    grad = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    gp = grad.load()
    for yy in range(h):
        t = yy / max(1, h - 1)
        r = int(round(top[0] + (bot[0] - top[0]) * t))
        g = int(round(top[1] + (bot[1] - top[1]) * t))
        b = int(round(top[2] + (bot[2] - top[2]) * t))
        for xx in range(w):
            gp[xx, yy] = (r, g, b, 255)

    mask = Image.new("L", (w, h), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, w - 1, h - 1), radius=rx, fill=255)
    bar_img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    bar_img.paste(grad, (0, 0), mask)
    img.paste(bar_img, (x, y), bar_img)
    return img.resize((canvas_w, canvas_h), Image.Resampling.LANCZOS)


def build_variant(*, dark: bool) -> None:
    prefix = "dark-" if dark else ""
    d_fill = "#F4F7F5" if dark else "#192232"
    d_svg = write_layer_svgs(d_fill, prefix)
    d_img = render_d_png(d_svg, OUT / f"{prefix}layer-d.png")
    w, h = d_img.size
    # Force exact scale size
    target = (int(664 * SCALE), int(761 * SCALE))
    if d_img.size != target:
        d_img = d_img.resize(target, Image.Resampling.LANCZOS)
        d_img.save(OUT / f"{prefix}layer-d.png")
        w, h = d_img.size

    bar_imgs: list[tuple[Image.Image, tuple[int, int, int, int]]] = []
    for bar in BARS:
        layer = draw_bar_layer(w, h, bar, scale=SCALE)
        layer.save(OUT / f"{prefix}layer-bar-{bar['id']}.png")
        bbox = layer.getbbox()
        if bbox:
            bar_imgs.append((layer, bbox))

    frames: list[Image.Image] = []
    steps = 28
    for i in range(steps):
        t = i / (steps - 1)
        e = 1 - (1 - t) ** 3
        frame = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        frame.alpha_composite(d_img)
        for bi, (layer, (x0, y0, x1, y1)) in enumerate(bar_imgs):
            local = max(0.0, min(1.0, (e - bi * 0.08) / 0.84))
            local = 1 - (1 - local) ** 3
            grow_h = max(1, int(round((y1 - y0) * local)))
            crop = layer.crop((x0, y1 - grow_h, x1, y1))
            frame.alpha_composite(crop, (x0, y1 - grow_h))
        frames.append(frame)

    for _ in range(12):
        frames.append(frames[-1].copy())

    webp = OUT / ("logo-grow-dark.webp" if dark else "logo-grow.webp")
    frames[0].save(
        webp,
        save_all=True,
        append_images=frames[1:],
        duration=36,
        loop=0,
        lossless=True,
    )
    gif = OUT / ("logo-grow-dark.gif" if dark else "logo-grow.gif")
    transparent = Image.new("RGBA", frames[0].size, (0, 0, 0, 0))
    gif_frames = [
        Image.alpha_composite(transparent, f).convert("P", palette=Image.ADAPTIVE, colors=255)
        for f in frames
    ]
    gif_frames[0].save(
        gif,
        save_all=True,
        append_images=gif_frames[1:],
        duration=36,
        loop=0,
        transparency=0,
        disposal=2,
    )
    print("ok", webp.name, f"{w}x{h}", "svg+png layers")


def main() -> None:
    OUT.mkdir(exist_ok=True)
    if not SRC_SVG.is_file():
        raise SystemExit(f"missing {SRC_SVG}")
    build_variant(dark=False)
    build_variant(dark=True)


if __name__ == "__main__":
    main()
