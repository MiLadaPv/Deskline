# Deskline

Local-first Windows productivity tracker by **AndalusGames**.

**One line:** Time Doctor–style focus tracking — data stays on your PC.

## Try it

1. **Chrome extension** — [extension/](extension/) (Web Store listing: [docs/CHROME_WEB_STORE.md](docs/CHROME_WEB_STORE.md)) or `scripts/pack_extension.ps1`.
2. **Desktop** — download from [GitHub Releases](https://github.com/MiLadaPv/Deskline/releases/latest) or build with `scripts/prepare_release.ps1`.

Sale / GTM: [docs/pitch.md](docs/pitch.md) · [docs/GTM_90.md](docs/GTM_90.md)

## Plans

| | **Free** | **Pro** | **Team** |
|--|----------|---------|----------|
| Tracking, focus reports, tray | Yes | Yes | Yes |
| History | 14 days | Unlimited | Unlimited |
| Projects | Up to 3 | Unlimited | Unlimited |
| Screenshots | No | Yes | Yes |
| Export JSON/CSV | No | Yes | Yes |
| Company LAN hub | No | No | **Yes** |

14-day **Pro trial** starts on first launch. Buy via Lemon Squeezy and paste the license key in Settings. See [docs/LEMON_SQUEEZY.md](docs/LEMON_SQUEEZY.md).

## Desktop app

Normal launch opens a **native window** (`deskline-desktop.exe`), not Chrome/Edge.

```bat
Deskline.bat
```

Or: `powershell -ExecutionPolicy Bypass -File scripts\run_desktop.ps1`

Dashboard: http://127.0.0.1:8787 · Marketing: http://127.0.0.1:8787/welcome · Compare: http://127.0.0.1:8787/docs/compare

## Privacy

- Data: `%LOCALAPPDATA%\Deskline`
- Policy: [docs/PRIVACY_POLICY.md](docs/PRIVACY_POLICY.md)
- No activity cloud sync; license validation only when activating Pro/Team
- Autostart off by default

## Installer

```bat
build_installer.bat
```

Or full prep: `powershell -ExecutionPolicy Bypass -File scripts\prepare_release.ps1`

Sign before public release: [docs/SIGNING.md](docs/SIGNING.md). Checklist: [docs/PUBLISH_CHECKLIST.md](docs/PUBLISH_CHECKLIST.md).

## Develop / test

```bat
python -m pytest -q
```

## Not included (by design)

- Keylogging / clipboard / mic
- Stealth remote sync / mandatory cloud
- DLP / live screen video walls
