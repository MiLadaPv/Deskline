"""Splash WebP must be high-FPS (Nano Banana), not a 7-step slideshow."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ANIM = ROOT / "web" / "static" / "img" / "logo-anim"


def _anmf_durations(path: Path) -> list[int]:
    data = path.read_bytes()
    durs: list[int] = []
    i = 0
    while True:
        j = data.find(b"ANMF", i)
        if j < 0:
            break
        size = int.from_bytes(data[j + 4 : j + 8], "little")
        payload = data[j + 8 : j + 8 + size]
        if len(payload) >= 16:
            dur = payload[12] | (payload[13] << 8) | (payload[14] << 16)
            durs.append(dur)
        i = j + 8 + size
    return durs


def test_logo_grow_webp_is_high_fps():
    for name in ("logo-grow.webp", "logo-grow-dark.webp"):
        path = ANIM / name
        assert path.is_file(), name
        durs = _anmf_durations(path)
        assert len(durs) >= 48, f"{name} too few frames: {len(durs)}"
        # Majority of frames should be ~60fps (16–20ms)
        short = [d for d in durs if 14 <= d <= 20]
        assert len(short) >= 40, f"{name} not high-FPS: {sorted(set(durs))}"
        assert sum(durs) >= 1500
