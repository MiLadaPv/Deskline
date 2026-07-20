# Deskline

Local-first Windows productivity tracker. Your activity stays on your PC — no cloud, no Telegram, no hidden agents.

## What it does

- Tracks which apps you use and for how long
- Infers sites from browser window titles
- Optional screenshots (interval + app switch)
- Daily focus report on a local dashboard
- System tray: **Recording** / **Paused**

## Desktop app (Tauri)

Native window around the same local tracker:

```bat
cd /d D:\Projects\Deskline\deskline-desktop
npm install
npm run dev
```

Or:

```bat
powershell -ExecutionPolicy Bypass -File scripts\run_desktop.ps1
```

Release build (NSIS/MSI):

```bat
cd /d D:\Projects\Deskline\deskline-desktop
npm run build
```

Details: [deskline-desktop/README.md](deskline-desktop/README.md)

## Privacy

- Data directory: `%LOCALAPPDATA%\Deskline`
- Dashboard binds to `127.0.0.1:8787` only
- Autostart is off by default and uses a normal Run key named `Deskline`

## Install (normal Windows installer)

Run this file:

**`D:\Projects\Deskline\release\DesklineSetup-0.1.0.exe`**

It installs like a regular Windows program (wizard, Start Menu, desktop shortcut, uninstall from Settings).

To rebuild the installer later:

```bat
build_installer.bat
```

## Alternative: script install (developers)

Double-click **`install.bat`** if you prefer the Python/venv installer.

## Run without installer

```bat
cd /d D:\Projects\Deskline
python -m pip install -r requirements.txt
Deskline.bat
```

Or: `start.bat` / `python -m deskline`

Dashboard: http://127.0.0.1:8787

## Controls

- Tray menu: Open dashboard / Pause / Resume / Quit
- Dashboard Settings: screenshot interval, autostart, clear local data

## Develop / test

```bat
python -m pytest -q
```

## Not included (by design)

- Browser extension (later)
- Keylogging / clipboard / mic
- Remote sync or stealth persistence
