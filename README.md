# Deskline

Local-first Windows productivity tracker by **AndalusGames**. Activity stays on your PC.

## Try it (Time Doctor–style funnel)

1. **Chrome extension** — load [`extension/`](extension/) unpacked for browser-only tracking ([extension/README.md](extension/README.md)).
2. **Desktop app** — native Windows window for all apps, optional screenshots, tray Recording/Paused.

Sale one-pager: [docs/pitch.md](docs/pitch.md)

## Plans

| | **Free** | **Pro** |
|--|----------|---------|
| Tracking, focus reports, tray | Yes | Yes |
| History | 14 days | Unlimited |
| Projects | Up to 3 | Unlimited |
| Screenshots | No | Yes |
| Export JSON/CSV | No | Yes |
| Company LAN hub | Later (**Team**) | Later (**Team**) |

14-day **Pro trial** starts on first launch. Buy via Lemon Squeezy and paste the license key in Settings. See [docs/LEMON_SQUEEZY.md](docs/LEMON_SQUEEZY.md).

## Desktop app

Normal launch opens a **native window** (`deskline-desktop.exe`), not Chrome/Edge.

```bat
Deskline.bat
```

Or: `powershell -ExecutionPolicy Bypass -File scripts\run_desktop.ps1`

First-time script install (copies Tauri shell + Python venv):

```bat
install.bat
```

Requires a built shell (`cd deskline-desktop && npm run build`). If the backend fails, Deskline shows an error dialog and writes `%LOCALAPPDATA%\Deskline\desktop.log` — it will not open a blank window.

Dashboard: http://127.0.0.1:8787 · Marketing: http://127.0.0.1:8787/welcome

## Browser extension (Chrome)

```text
chrome://extensions → Developer mode → Load unpacked → extension/
```

Popup: Pause/Resume, today’s browser time, **Get Desktop** when the local API is offline. When Desktop is running on `:8787`, tab segments sync via `/api/extension/event`.

## Privacy

- Data: `%LOCALAPPDATA%\Deskline`
- No activity cloud sync; license validation only when activating Pro
- Autostart off by default (`Deskline` Run key)

## Installer (buyer artifact)

```bat
build_installer.bat
```

Builds Tauri shell + PyInstaller backend, then Inno Setup → `release\DesklineSetup-*.exe`. Shortcuts launch **`deskline-desktop.exe`**. Sign before public release: [docs/SIGNING.md](docs/SIGNING.md). Publish checklist: [docs/PUBLISH_CHECKLIST.md](docs/PUBLISH_CHECKLIST.md).

Extension zip for buyers: zip the `extension/` folder.

## Develop / test

```bat
python -m pytest -q
```

## Not included (by design)

- Keylogging / clipboard / mic
- Stealth remote sync / mandatory cloud
