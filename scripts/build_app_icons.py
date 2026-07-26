"""Build Windows/Tauri/extension icons from the Deskline D mark."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "web" / "static" / "img" / "logo-dark.png"
ASSETS = ROOT / "assets"
TAURI = ROOT / "deskline-desktop" / "src-tauri" / "icons"
EXT = ROOT / "extension" / "icons"


def _load_mark() -> Image.Image:
    im = Image.open(SRC).convert("RGBA")
    # Knock near-black canvas to transparent if any
    px = im.load()
    assert px is not None
    for y in range(im.height):
        for x in range(im.width):
            r, g, b, a = px[x, y]
            if a > 0 and r < 18 and g < 18 and b < 18:
                px[x, y] = (0, 0, 0, 0)
    bbox = im.getbbox()
    if bbox:
        im = im.crop(bbox)
    return im


def _icon_tile(mark: Image.Image, size: int, *, rounded: bool = True) -> Image.Image:
    """Square app icon: dark rounded plate + centered D mark."""
    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(canvas)
    pad = max(1, size // 16)
    radius = size // 5 if rounded else 0
    # Brand dark plate
    draw.rounded_rectangle(
        (pad, pad, size - 1 - pad, size - 1 - pad),
        radius=radius,
        fill=(15, 18, 24, 255),
    )
    # Fit mark inside with margin
    inner = int(size * 0.72)
    m = mark.copy()
    m.thumbnail((inner, inner), Image.Resampling.LANCZOS)
    x = (size - m.width) // 2
    y = (size - m.height) // 2
    canvas.alpha_composite(m, (x, y))
    return canvas


def _save_ico(path: Path, mark: Image.Image) -> None:
    sizes = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    largest = _icon_tile(mark, 256)
    largest.save(path, format="ICO", sizes=sizes)
    print("wrote", path, path.stat().st_size)


def main() -> None:
    if not SRC.exists():
        raise SystemExit(f"missing {SRC}")
    mark = _load_mark()
    ASSETS.mkdir(exist_ok=True)
    TAURI.mkdir(parents=True, exist_ok=True)
    EXT.mkdir(parents=True, exist_ok=True)

    # Master PNG for docs / installer preview
    master = _icon_tile(mark, 1024)
    master.save(ASSETS / "deskline-icon.png", optimize=True)
    _save_ico(ASSETS / "deskline.ico", mark)

    # Tray: smaller, slightly tighter
    tray = _icon_tile(mark, 64)
    tray.save(ASSETS / "tray.png", optimize=True)

    # Tauri set
    for name, size in (
        ("32x32.png", 32),
        ("64x64.png", 64),
        ("128x128.png", 128),
        ("128x128@2x.png", 256),
        ("icon.png", 512),
    ):
        _icon_tile(mark, size).save(TAURI / name, optimize=True)
    _save_ico(TAURI / "icon.ico", mark)

    # Store / square logos (Windows)
    for name, size in (
        ("Square30x30Logo.png", 30),
        ("Square44x44Logo.png", 44),
        ("Square71x71Logo.png", 71),
        ("Square89x89Logo.png", 89),
        ("Square107x107Logo.png", 107),
        ("Square142x142Logo.png", 142),
        ("Square150x150Logo.png", 150),
        ("Square284x284Logo.png", 284),
        ("Square310x310Logo.png", 310),
        ("StoreLogo.png", 50),
    ):
        _icon_tile(mark, size).save(TAURI / name, optimize=True)

    # Extension icons
    for size in (16, 32, 48, 128):
        _icon_tile(mark, size).save(EXT / f"icon{size}.png", optimize=True)

    print("ok icons from", SRC.name)


if __name__ == "__main__":
    main()
