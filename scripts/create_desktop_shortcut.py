"""Create Deskline.lnk on the real Windows Desktop (OneDrive-aware)."""
from __future__ import annotations

import sys
from pathlib import Path


def desktop_dir() -> Path:
    import ctypes
    from ctypes import wintypes

    buf = ctypes.create_unicode_buffer(wintypes.MAX_PATH)
    # CSIDL_DESKTOPDIRECTORY = 0x10
    hr = ctypes.windll.shell32.SHGetFolderPathW(None, 0x10, None, 0, buf)
    if hr != 0:
        raise OSError(f"SHGetFolderPathW failed: {hr}")
    return Path(buf.value)


def create_shortcut(lnk: Path, target: Path, workdir: Path, icon: Path | None) -> None:
    import win32com.client  # type: ignore

    lnk.parent.mkdir(parents=True, exist_ok=True)
    if lnk.exists():
        lnk.unlink()
    shell = win32com.client.Dispatch("WScript.Shell")
    sc = shell.CreateShortcut(str(lnk))
    sc.TargetPath = str(target)
    sc.WorkingDirectory = str(workdir)
    sc.WindowStyle = 1
    sc.Description = "Deskline local productivity tracker"
    if icon and icon.is_file():
        sc.IconLocation = f"{icon},0"
    sc.Save()


def main() -> int:
    install = Path.home() / "AppData" / "Local" / "Programs" / "Deskline"
    target = install / "deskline-desktop.exe"
    if not target.is_file():
        print("ERR missing deskline-desktop.exe", file=sys.stderr)
        return 1
    icon = install / "deskline.ico"
    if not icon.is_file():
        src = Path(__file__).resolve().parents[1] / "assets" / "deskline.ico"
        if src.is_file():
            icon.write_bytes(src.read_bytes())
    desk = desktop_dir()
    # Also classic Desktop (non-OneDrive)
    classic = Path.home() / "Desktop"
    paths = []
    for d in (desk, classic):
        try:
            if d.is_dir():
                paths.append(d / "Deskline.lnk")
        except OSError:
            continue
    # unique
    seen = set()
    uniq = []
    for p in paths:
        key = str(p).casefold()
        if key in seen:
            continue
        seen.add(key)
        uniq.append(p)

    ok = 0
    made: list[Path] = []
    for lnk in uniq:
        try:
            create_shortcut(lnk, target, install, icon if icon.is_file() else None)
            print("OK", lnk.name)
            ok += 1
            made.append(lnk)
        except Exception as e:
            print("FAIL COM", type(e).__name__, file=sys.stderr)

    # OneDrive Desktop often rejects WScript.Shell.Save — binary-copy a working .lnk.
    if made:
        import shutil

        for dest_dir in (desk, classic):
            try:
                dest = dest_dir / "Deskline.lnk"
                if dest.is_file():
                    continue
                shutil.copy2(made[0], dest)
                print("OK copied")
                ok += 1
            except Exception:
                pass
    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
