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
| Setup (Inno) | `release/DesklineSetup-0.5.0.exe` |
| Tauri NSIS/MSI | `deskline-desktop/src-tauri/target/release/bundle/...` |

## Sign command (example)

```bat
signtool sign /fd SHA256 /tr http://timestamp.digicert.com /td SHA256 /a DesklineSetup-0.5.0.exe
signtool verify /pa /v DesklineSetup-0.5.0.exe
```

## Release pipeline order

1. Bump `__version__`, `pyproject.toml`, `installer/deskline.iss`, `tauri.conf.json` to the same version.
2. `python -m pytest -q`
3. `scripts/build_installer.ps1` (or Tauri `npm run build`)
4. Sign all shipping binaries
5. Upload to GitHub Releases (`AndalusGames/Deskline`) with SHA256 checksums
6. Update marketing `/welcome` download link

## Not done in-repo

Certificate purchase, private keys, and live SmartScreen reputation warming are
out of band — keep secrets out of git.
