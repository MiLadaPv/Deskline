"""Assemble cinematic Nano Banana 'Aurora Rise' splash into WebP."""

from __future__ import annotations

import shutil
from pathlib import Path

from PIL import Image, ImageFilter

ROOT = Path(__file__).resolve().parents[1]
IMG = ROOT / "web" / "static" / "img"
OUT = IMG / "logo-anim"
ASSETS = Path(r"C:\Users\mmher\.cursor\projects\d-vdip5-rdp\assets")
SRC_DIR = OUT / "nano-beauty"

FRAME_NAMES = [
    "beauty-f1.png",
    "beauty-f2.png",
    "beauty-f3.png",
    "beauty-f4.png",
    "beauty-f5.png",
    "beauty-f6.png",
    "beauty-f7.png",
]

SIZE = (720, 820)


def _knockout_black(im: Image.Image, thr: int = 22) -> Image.Image:
    im = im.convert("RGBA")
    px = im.load()
    assert px is not None
    for y in range(im.height):
        for x in range(im.width):
            r, g, b, a = px[x, y]
            if a < 8:
                continue
            # Keep soft glow (slightly above pure black) — only punch dead black
            if r <= thr and g <= thr and b <= thr and (max(r, g, b) - min(r, g, b)) < 12:
                px[x, y] = (0, 0, 0, 0)
    return im


def _fit(im: Image.Image, size: tuple[int, int] = SIZE) -> Image.Image:
    canvas = Image.new("RGBA", size, (0, 0, 0, 0))
    work = im
    bbox = im.getbbox()
    if bbox:
        work = im.crop(bbox)
    work = work.copy()
    work.thumbnail((size[0] - 40, size[1] - 40), Image.Resampling.LANCZOS)
    x = (size[0] - work.width) // 2
    y = (size[1] - work.height) // 2
    canvas.alpha_composite(work, (x, y))
    return canvas


def _recolor_letter(im: Image.Image, rgb: tuple[int, int, int]) -> Image.Image:
    out = im.copy()
    px = out.load()
    assert px is not None
    tr, tg, tb = rgb
    for y in range(out.height):
        for x in range(out.width):
            r, g, b, a = px[x, y]
            if a < 10:
                continue
            vivid = (max(r, g, b) - min(r, g, b)) > 28 and max(r, g, b) > 45
            if vivid:
                continue
            # soft aurora / gray glow: keep if low-sat mid tones? recolor letter-like bright neutrals
            lum = 0.2126 * r + 0.7152 * g + 0.0722 * b
            if lum < 40:
                continue
            px[x, y] = (tr, tg, tb, a)
    return out


def _build_webp(frames: list[Image.Image], path: Path) -> None:
    # Cinematic timing (ms): bloom → ghost → D → bars → hold
    base_dur = [120, 140, 160, 110, 110, 120, 150]
    seq: list[Image.Image] = []
    durs: list[int] = []
    for i, fr in enumerate(frames):
        seq.append(fr)
        durs.append(base_dur[i] if i < len(base_dur) else 100)
    # hold final with soft settle
    for _ in range(12):
        seq.append(frames[-1].copy())
        durs.append(70)
    seq[0].save(
        path,
        save_all=True,
        append_images=seq[1:],
        duration=durs,
        loop=0,
        lossless=True,
        method=6,
    )
    print("wrote", path.name, "frames", len(seq))


def main() -> None:
    SRC_DIR.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(exist_ok=True)
    dark_frames: list[Image.Image] = []
    light_frames: list[Image.Image] = []
    for name in FRAME_NAMES:
        src = ASSETS / name
        if not src.exists():
            raise SystemExit(f"missing {src}")
        dst = SRC_DIR / name
        shutil.copy2(src, dst)
        raw = Image.open(src).convert("RGBA")
        raw = raw.resize((raw.width * 2, raw.height * 2), Image.Resampling.LANCZOS)
        cut = _knockout_black(raw)
        # slight soft edge polish
        a = cut.getchannel("A").filter(ImageFilter.GaussianBlur(0.45))
        r, g, b, _ = cut.split()
        cut = Image.merge("RGBA", (r, g, b, a))
        fitted = _fit(cut)
        dark_frames.append(_recolor_letter(fitted, (244, 247, 245)))
        light_frames.append(_recolor_letter(fitted, (25, 34, 50)))

    dark_frames[-1].save(OUT / "logo-splash-dark.png", optimize=True)
    light_frames[-1].save(OUT / "logo-splash.png", optimize=True)
    _build_webp(dark_frames, OUT / "logo-grow-dark.webp")
    _build_webp(light_frames, OUT / "logo-grow.webp")
    print("ok Aurora Rise splash")


if __name__ == "__main__":
    main()
