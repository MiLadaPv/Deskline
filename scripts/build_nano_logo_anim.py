"""Assemble Nano Banana logo frames into splash WebP (dark + light)."""

from __future__ import annotations

import shutil
from pathlib import Path

from PIL import Image, ImageChops

ROOT = Path(__file__).resolve().parents[1]
IMG = ROOT / "web" / "static" / "img"
OUT = IMG / "logo-anim"
ASSETS = Path(r"C:\Users\mmher\.cursor\projects\d-vdip5-rdp\assets")

FRAME_NAMES = [
    "logo-anim-f1.png",
    "logo-anim-f2.png",
    "logo-anim-f3.png",
    "logo-anim-f4.png",
    "logo-anim-f5.png",
]

SIZE = (664, 761)


def _knockout_black(im: Image.Image, thr: int = 28) -> Image.Image:
    im = im.convert("RGBA")
    px = im.load()
    assert px is not None
    w, h = im.size
    for y in range(h):
        for x in range(w):
            r, g, b, a = px[x, y]
            if a < 8:
                continue
            if r <= thr and g <= thr and b <= thr and (max(r, g, b) - min(r, g, b)) < 20:
                px[x, y] = (0, 0, 0, 0)
    return im


def _fit(im: Image.Image, size: tuple[int, int] = SIZE) -> Image.Image:
    canvas = Image.new("RGBA", size, (0, 0, 0, 0))
    trimmed = im
    bbox = im.getbbox()
    if bbox:
        trimmed = im.crop(bbox)
    trimmed = trimmed.copy()
    trimmed.thumbnail((size[0] - 48, size[1] - 48), Image.Resampling.LANCZOS)
    x = (size[0] - trimmed.width) // 2
    y = (size[1] - trimmed.height) // 2
    canvas.alpha_composite(trimmed, (x, y))
    return canvas


def _recolor_letter(im: Image.Image, rgb: tuple[int, int, int]) -> Image.Image:
    out = im.copy()
    px = out.load()
    assert px is not None
    tr, tg, tb = rgb
    for y in range(out.height):
        for x in range(out.width):
            r, g, b, a = px[x, y]
            if a < 8:
                continue
            # keep colorful bars
            if (max(r, g, b) - min(r, g, b)) > 35 and max(r, g, b) > 50:
                continue
            px[x, y] = (tr, tg, tb, a)
    return out


def _copy_sources() -> list[Path]:
    OUT.mkdir(exist_ok=True)
    src_dir = IMG / "logo-anim" / "nano-frames"
    src_dir.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    for name in FRAME_NAMES:
        src = ASSETS / name
        if not src.exists():
            raise SystemExit(f"missing Nano Banana frame: {src}")
        dst = src_dir / name
        shutil.copy2(src, dst)
        paths.append(dst)
    return paths


def build_webp(frames: list[Image.Image], path: Path, *, hold: int = 10) -> None:
    seq = list(frames)
    for _ in range(hold):
        seq.append(frames[-1].copy())
    # ease-in: repeat early frames less, mid more briefly
    durations = [70, 70, 75, 80, 90] + [55] * hold
    while len(durations) < len(seq):
        durations.append(55)
    seq[0].save(
        path,
        save_all=True,
        append_images=seq[1:],
        duration=durations[: len(seq)],
        loop=0,
        lossless=True,
        method=6,
    )
    print("wrote", path.name, "frames", len(seq), "corner_a", seq[-1].getpixel((0, 0))[3])


def main() -> None:
    paths = _copy_sources()
    dark_frames: list[Image.Image] = []
    light_frames: list[Image.Image] = []
    for p in paths:
        raw = Image.open(p).convert("RGBA")
        # Upscale soft then fit for cleaner AA
        raw = raw.resize((raw.width * 2, raw.height * 2), Image.Resampling.LANCZOS)
        cut = _knockout_black(raw)
        fitted = _fit(cut)
        dark_frames.append(_recolor_letter(fitted, (244, 247, 245)))
        light_frames.append(_recolor_letter(fitted, (25, 34, 50)))

    # Also export static splash PNGs from final frame
    dark_frames[-1].save(OUT / "logo-splash-dark.png", optimize=True)
    light_frames[-1].save(OUT / "logo-splash.png", optimize=True)

    build_webp(dark_frames, OUT / "logo-grow-dark.webp")
    build_webp(light_frames, OUT / "logo-grow.webp")


if __name__ == "__main__":
    main()
