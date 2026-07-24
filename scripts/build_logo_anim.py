"""Build Deskline logo bar-grow animation from the official logo.png."""

from __future__ import annotations

from pathlib import Path

from PIL import Image

SRC = Path(__file__).resolve().parents[1] / "web" / "static" / "img" / "logo.png"
SRC_DARK = Path(__file__).resolve().parents[1] / "web" / "static" / "img" / "logo-dark.png"
OUT = Path(__file__).resolve().parents[1] / "web" / "static" / "img" / "logo-anim"


def build_from(src: Path, stem: str) -> None:
    im = Image.open(src).convert("RGBA")
    w, h = im.size
    sx, sy = w / 664.0, h / 761.0
    bars_vb = [
        (155, 498, 85, 146),
        (252, 407, 86, 236),
        (352, 309, 86, 320),
    ]

    def px_box(box: tuple[int, int, int, int]) -> tuple[int, int, int, int]:
        x, y, bw, bh = box
        return (
            int(round(x * sx)),
            int(round(y * sy)),
            int(round((x + bw) * sx)),
            int(round((y + bh) * sy)),
        )

    full = im.copy()
    d_only = im.copy()
    bar_layers: list[tuple[Image.Image, tuple[int, int, int, int]]] = []

    for box in bars_vb:
        x0, y0, x1, y1 = px_box(box)
        layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        crop = full.crop((x0, y0, x1, y1)).copy()
        pix = crop.load()
        for yy in range(crop.size[1]):
            for xx in range(crop.size[0]):
                r, g, b, a = pix[xx, yy]
                if a < 20:
                    pix[xx, yy] = (0, 0, 0, 0)
                    continue
                vivid = (max(r, g, b) - min(r, g, b) > 20) or g > 100 or b > 140
                # dark-theme D is light; bars still vivid
                if not vivid and max(r, g, b) > 200:
                    pix[xx, yy] = (0, 0, 0, 0)
                    continue
                if not vivid:
                    pix[xx, yy] = (0, 0, 0, 0)
        layer.paste(crop, (x0, y0), crop)
        bar_layers.append((layer, (x0, y0, x1, y1)))
        d_pix = d_only.load()
        lp = layer.load()
        for yy in range(y0, y1):
            for xx in range(x0, x1):
                if lp[xx, yy][3] > 20:
                    d_pix[xx, yy] = (0, 0, 0, 0)

    prefix = "" if stem == "light" else "dark-"
    d_only.save(OUT / f"{prefix}layer-d.png")
    for i, (layer, _) in enumerate(bar_layers, 1):
        layer.save(OUT / f"{prefix}layer-bar-{i}.png")

    frames: list[Image.Image] = []
    steps = 24
    for i in range(steps):
        t = i / (steps - 1)
        e = 1 - (1 - t) ** 3
        frame = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        frame.alpha_composite(d_only)
        for bi, (layer, (x0, y0, x1, y1)) in enumerate(bar_layers):
            local = max(0.0, min(1.0, (e - bi * 0.08) / 0.84))
            local = 1 - (1 - local) ** 3
            grow_h = max(1, int(round((y1 - y0) * local)))
            bar_crop = layer.crop((x0, y1 - grow_h, x1, y1))
            frame.alpha_composite(bar_crop, (x0, y1 - grow_h))
        frames.append(frame)

    for _ in range(10):
        frames.append(frames[-1].copy())

    name = "logo-grow.webp" if stem == "light" else "logo-grow-dark.webp"
    webp = OUT / name
    frames[0].save(
        webp,
        save_all=True,
        append_images=frames[1:],
        duration=40,
        loop=0,
        lossless=True,
    )
    gif_name = "logo-grow.gif" if stem == "light" else "logo-grow-dark.gif"
    gif = OUT / gif_name
    gif_frames = [f.convert("P", palette=Image.ADAPTIVE, colors=255) for f in frames]
    gif_frames[0].save(
        gif,
        save_all=True,
        append_images=gif_frames[1:],
        duration=40,
        loop=0,
        transparency=0,
        disposal=2,
    )
    print("ok", webp, gif)


def main() -> None:
    OUT.mkdir(exist_ok=True)
    build_from(SRC, "light")
    if SRC_DARK.is_file():
        build_from(SRC_DARK, "dark")


if __name__ == "__main__":
    main()
