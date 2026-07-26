# Code signing checklist (Windows Authenticode)

Deskline installers must be signed before public download. Unsigned builds trigger
SmartScreen warnings and block conversion.

**New to this?** Start with the beginner walkthrough: **[SIGNING_BEGINNER.md](SIGNING_BEGINNER.md)**  
(OV vs EV, buy/install cert, `prepare_release` → `sign_release` → GitHub Release).

## Prerequisites

1. Buy an **OV** or **EV** Authenticode certificate for **AndalusGames** (DigiCert, Sectigo, SSL.com, etc.).
2. Install the certificate on the release machine (or use a cloud HSM / Azure Trusted Signing).
3. Install Windows SDK so `signtool.exe` is available.
4. Install [Inno Setup 6](https://jrsoftware.org/isinfo.php) for Setup builds.

## What to sign

| Artifact | Path |
|----------|------|
| Setup (Inno) | `release/DesklineSetup-<version>.exe` |
| Tracker binary | `dist/Deskline/Deskline.exe` (if present after build) |
| Tauri shell | `dist/Deskline/deskline-desktop.exe` (if present after build) |

## Scripts (recommended)

```powershell
cd D:\Projects\Deskline
powershell -ExecutionPolicy Bypass -File scripts\prepare_release.ps1
powershell -ExecutionPolicy Bypass -File scripts\sign_release.ps1
# if several certs:
# powershell -ExecutionPolicy Bypass -File scripts\sign_release.ps1 -Thumbprint YOURTHUMBPRINT
```

## Manual sign command

```bat
signtool sign /fd SHA256 /tr http://timestamp.digicert.com /td SHA256 /a release\DesklineSetup-0.5.30.exe
signtool verify /pa /v release\DesklineSetup-0.5.30.exe
```

## Release pipeline order

1. Bump `__version__`, `pyproject.toml`, `installer/deskline.iss`, `tauri.conf.json`, `extension/manifest.json`.
2. `python -m pytest -q`
3. `scripts\prepare_release.ps1`
4. `scripts\sign_release.ps1`
5. Upload to GitHub Releases (`https://github.com/MiLadaPv/Deskline`) with `SHA256SUMS.txt`
6. Confirm `/welcome` download CTA → `releases/latest`

## Not done in-repo

Certificate purchase, private keys, and live SmartScreen reputation warming are
out of band — keep secrets out of git.
