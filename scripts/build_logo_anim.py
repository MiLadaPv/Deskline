"""Build splash logo animation from official logo.png (no SVG re-render)."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageChops, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
IMG = ROOT / "web" / "static" / "img"
OUT = IMG / "logo-anim"

BARS = [
    (155, 498, 85, 146, 42.5),
    (252, 407, 86, 236, 43.0),
    (352, 309, 86, 320, 43.0),
]


def _bar_mask(size: tuple[int, int], box: tuple[float, ...], scale: float) -> Image.Image:
    w, h = size
    x, y, bw, bh, rx = box
    x0 = int(round(x * scale))
    y0 = int(round(y * scale))
    x1 = int(round((x + bw) * scale))
    y1 = int(round((y + bh) * scale))
    r = int(round(min(rx * scale, (x1 - x0) / 2, (y1 - y0) / 2)))
    ss = 3
    big = Image.new("L", (w * ss, h * ss), 0)
    ImageDraw.Draw(big).rounded_rectangle(
        (x0 * ss, y0 * ss, x1 * ss - 1, y1 * ss - 1),
        radius=max(1, r * ss),
        fill=255,
    )
    return big.resize((w, h), Image.Resampling.LANCZOS)


def _erase_masked(img: Image.Image, mask: Image.Image) -> Image.Image:
    r, g, b, a = img.split()
    keep = mask.point(lambda v: 0 if v > 32 else 255)
    a = ImageChops.multiply(a, keep)
    out = Image.merge("RGBA", (r, g, b, a))
    return out


def build_from(src: Path, stem: str) -> None:
    logo = Image.open(src).convert("RGBA")
    w, h = logo.size
    scale = w / 664.0
    masks = [_bar_mask((w, h), box, scale) for box in BARS]

    d_only = logo
    for m in masks:
        d_only = _erase_masked(d_only, m)

    prefix = "" if stem == "light" else "dark-"
    d_only.save(OUT / f"{prefix}layer-d.png")
    for i, mask in enumerate(masks, 1):
        layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        layer.paste(logo, (0, 0), mask)
        layer.save(OUT / f"{prefix}layer-bar-{i}.png")

    frames: list[Image.Image] = []
    steps = 26
    for i in range(steps):
        t = i / (steps - 1)
        e = 1 - (1 - t) ** 3
        frame = d_only.copy()
        for bi, (box, mask) in enumerate(zip(BARS, masks)):
            local = max(0.0, min(1.0, (e - bi * 0.1) / 0.8))
            local = 1 - (1 - local) ** 3
            x, y, bw, bh, _rx = box
            x0 = int(round(x * scale))
            y0 = int(round(y * scale))
            x1 = int(round((x + bw) * scale))
            y1 = int(round((y + bh) * scale))
            grow = max(1, int(round((y1 - y0) * local)))
            band = Image.new("L", (w, h), 0)
            ImageDraw.Draw(band).rectangle((x0, y1 - grow, x1, y1), fill=255)
            reveal = ImageChops.multiply(mask, band)
            piece = Image.new("RGBA", (w, h), (0, 0, 0, 0))
            piece.paste(logo, (0, 0), reveal)
            frame.alpha_composite(piece)
        frames.append(frame)

    for _ in range(14):
        frames.append(frames[-1].copy())

    corner = frames[0].getpixel((0, 0))
    if corner[3] > 10:
        raise RuntimeError(f"expected transparent corner, got {corner}")

    webp = OUT / ("logo-grow.webp" if stem == "light" else "logo-grow-dark.webp")
    frames[0].save(
        webp,
        save_all=True,
        append_images=frames[1:],
        duration=38,
        loop=0,
        lossless=True,
    )
    # Skip low-quality GIF for splash; keep a short preview only from final frames quality webp.
    print("ok", webp.name, logo.size, "corner_alpha", corner[3])


def main() -> None:
    OUT.mkdir(exist_ok=True)
    build_from(IMG / "logo.png", "light")
    build_from(IMG / "logo-dark.png", "dark")


if __name__ == "__main__":
    main()
