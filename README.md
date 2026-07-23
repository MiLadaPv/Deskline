# Deskline

Local-first Windows productivity tracker by **AndalusGames**. Activity stays on your PC.

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

```bat
Deskline.bat
```

Or: `powershell -ExecutionPolicy Bypass -File scripts\run_desktop.ps1`

Dashboard: http://127.0.0.1:8787 · Marketing: http://127.0.0.1:8787/welcome

## Privacy

- Data: `%LOCALAPPDATA%\Deskline`
- No activity cloud sync; license validation only when activating Pro
- Autostart off by default (`Deskline` Run key)

## Installer

```bat
build_installer.bat
```

Produces `release\DesklineSetup-0.5.0.exe` (publisher AndalusGames). Sign before public release: [docs/SIGNING.md](docs/SIGNING.md). Publish checklist: [docs/PUBLISH_CHECKLIST.md](docs/PUBLISH_CHECKLIST.md).

## Develop / test

```bat
python -m pytest -q
```

## Not included (by design)

- Browser extension (later)
- Keylogging / clipboard / mic
- Stealth remote sync
