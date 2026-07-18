# Deskline

Local-first Windows productivity tracker. Your activity stays on your PC — no cloud, no Telegram, no hidden agents.

## What it does

- Tracks which apps you use and for how long
- Infers sites from browser window titles
- Optional screenshots (interval + app switch)
- Daily focus report on a local dashboard
- System tray: **Recording** / **Paused**

## Privacy

- Data directory: `%LOCALAPPDATA%\Deskline`
- Dashboard binds to `127.0.0.1:8787` only
- Autostart is off by default and uses a normal Run key named `Deskline`

## Setup

```bat
cd /d D:\Projects\Deskline
python -m pip install -r requirements.txt
python -m deskline
```

Or double-click `start.bat`.

Open http://127.0.0.1:8787 if the browser does not open.

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
