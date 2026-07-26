# Code signing checklist (Windows Authenticode)

Deskline installers must be signed before public download. Unsigned builds trigger
SmartScreen warnings and block conversion.

## Prerequisites

1. Buy an **OV** or **EV** Authenticode certificate for **AndalusGames** (DigiCert, Sectigo, SSL.com, etc.).
2. Install the certificate on the release machine (or use a cloud HSM / Azure Trusted Signing).
3. Install Windows SDK so `signtool.exe` is available.

## What to sign

| Artifact | Path |
|----------|------|
| Tracker binary | `dist/Deskline/Deskline.exe` (+ DLLs if required by policy) |
| Setup (Inno) | `release/DesklineSetup-<version>.exe` |
| Tauri shell | `deskline-desktop.exe` inside the staged app dir |

## Sign command (example)

```bat
signtool sign /fd SHA256 /tr http://timestamp.digicert.com /td SHA256 /a release\DesklineSetup-0.5.30.exe
signtool verify /pa /v release\DesklineSetup-0.5.30.exe
```

## Release pipeline order

1. Bump `__version__`, `pyproject.toml`, `installer/deskline.iss`, `tauri.conf.json`, `extension/manifest.json`.
2. `python -m pytest -q`
3. `powershell -ExecutionPolicy Bypass -File scripts\prepare_release.ps1`
4. Sign all shipping binaries
5. Upload to GitHub Releases (`https://github.com/MiLadaPv/Deskline`) with `SHA256SUMS.txt`
6. Confirm `/welcome` “Скачать” points at `releases/latest`

## Not done in-repo

Certificate purchase, private keys, and live SmartScreen reputation warming are
out of band — keep secrets out of git.
