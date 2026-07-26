"""Assemble cinematic Nano Banana 'Aurora Rise' splash into high-FPS WebP.

Upsamples 7 Nano Banana keyframes to ~60 fps via eased alpha blends so the
splash reads buttery-smooth instead of a 7-step slideshow.
"""

from __future__ import annotations

import math
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

# Target display cadence (ms). 16 ≈ 62.5 fps — max practical for animated WebP.
FRAME_MS = 16
# Grow phase length (ms) across keyframe path.
GROW_MS = 1100
# Hold final mark on screen (ms) before CSS fades the splash.
HOLD_MS = 900


def _knockout_black(im: Image.Image, thr: int = 22) -> Image.Image:
    im = im.convert("RGBA")
    px = im.load()
    assert px is not None
    for y in range(im.height):
        for x in range(im.width):
            r, g, b, a = px[x, y]
            if a < 8:
                continue
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
            lum = 0.2126 * r + 0.7152 * g + 0.0722 * b
            if lum < 40:
                continue
            px[x, y] = (tr, tg, tb, a)
    return out


def _ease_in_out(t: float) -> float:
    """Smoothstep — cinematic ease without hard steps."""
    t = max(0.0, min(1.0, t))
    return t * t * (3.0 - 2.0 * t)


def _blend(a: Image.Image, b: Image.Image, t: float) -> Image.Image:
    t = _ease_in_out(t)
    if t <= 0.001:
        return a.copy()
    if t >= 0.999:
        return b.copy()
    return Image.blend(a.convert("RGBA"), b.convert("RGBA"), t)


def _upsample_keys(keys: list[Image.Image], grow_ms: int, frame_ms: int) -> list[Image.Image]:
    """Dense frame list between keyframes at the target cadence."""
    if len(keys) < 2:
        return [keys[0].copy()] if keys else []
    n_grow = max(len(keys), int(round(grow_ms / frame_ms)))
    # Segment weights: linger slightly mid-bloom (bars rising).
    weights = [1.0, 1.15, 1.35, 1.25, 1.1, 1.0]
    while len(weights) < len(keys) - 1:
        weights.append(1.0)
    weights = weights[: len(keys) - 1]
    wsum = sum(weights)
    seg_frames = [max(2, int(round(n_grow * (w / wsum)))) for w in weights]
    # Fix rounding so total ≈ n_grow
    while sum(seg_frames) > n_grow and max(seg_frames) > 2:
        i = seg_frames.index(max(seg_frames))
        seg_frames[i] -= 1
    while sum(seg_frames) < n_grow:
        i = seg_frames.index(min(seg_frames))
        seg_frames[i] += 1

    out: list[Image.Image] = []
    for si, count in enumerate(seg_frames):
        a, b = keys[si], keys[si + 1]
        for j in range(count):
            t = j / count
            out.append(_blend(a, b, t))
    out.append(keys[-1].copy())
    return out


def _build_webp(keys: list[Image.Image], path: Path) -> None:
    motion = _upsample_keys(keys, GROW_MS, FRAME_MS)
    hold_n = max(8, int(round(HOLD_MS / FRAME_MS)))
    seq = motion + [keys[-1].copy() for _ in range(hold_n)]
    durs = [FRAME_MS] * len(seq)
    # Play once; browsers keep the last frame after the loop ends.
    seq[0].save(
        path,
        save_all=True,
        append_images=seq[1:],
        duration=durs,
        loop=1,
        lossless=False,
        quality=88,
        method=4,
        minimize_size=True,
    )
    total_ms = FRAME_MS * len(seq)
    print(
        f"wrote {path.name}: frames={len(seq)} "
        f"fps~={1000 / FRAME_MS:.0f} duration_ms~={total_ms}"
    )


def _load_key(name: str) -> Image.Image:
    local = SRC_DIR / name
    asset = ASSETS / name
    src = local if local.is_file() else asset
    if not src.is_file():
        raise SystemExit(f"missing keyframe {name} (looked in {local} and {asset})")
    if asset.is_file():
        SRC_DIR.mkdir(parents=True, exist_ok=True)
        shutil.copy2(asset, local)
    raw = Image.open(src).convert("RGBA")
    # Upscale source for cleaner downsample into canvas
    raw = raw.resize((raw.width * 2, raw.height * 2), Image.Resampling.LANCZOS)
    cut = _knockout_black(raw)
    a = cut.getchannel("A").filter(ImageFilter.GaussianBlur(0.45))
    r, g, b, _ = cut.split()
    cut = Image.merge("RGBA", (r, g, b, a))
    return _fit(cut)


def main() -> None:
    SRC_DIR.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(exist_ok=True)
    dark_keys: list[Image.Image] = []
    light_keys: list[Image.Image] = []
    for name in FRAME_NAMES:
        fitted = _load_key(name)
        dark_keys.append(_recolor_letter(fitted, (244, 247, 245)))
        light_keys.append(_recolor_letter(fitted, (25, 34, 50)))

    dark_keys[-1].save(OUT / "logo-splash-dark.png", optimize=True)
    light_keys[-1].save(OUT / "logo-splash.png", optimize=True)
    _build_webp(dark_keys, OUT / "logo-grow-dark.webp")
    _build_webp(light_keys, OUT / "logo-grow.webp")
    print("ok Aurora Rise splash @ ~60fps")


if __name__ == "__main__":
    main()
