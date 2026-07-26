# Deskline publish double-check

Use this before any public download link goes live. Current code version must match all packaging files.

## Product / freemium

- [ ] Fresh install shows onboarding once
- [ ] First 14 days: Pro trial (screenshots + export + unlimited history)
- [ ] After trial without key: Free limits (14d history, 3 projects, no screenshots)
- [ ] Activate `DESKLINE-PRO-DEV` / `DESKLINE-TEAM-DEV` only on dev builds; production uses Lemon Squeezy keys
- [ ] Company hub returns 402 on Free/Pro; works on Team
- [ ] Paywall modal appears on gated actions
- [ ] `/welcome#pricing` lists Free / Pro / Team
- [ ] Privacy/Terms + [PRIVACY_POLICY.md](PRIVACY_POLICY.md) are current

## Distribution

- [ ] `__version__` == `pyproject.toml` == `installer/deskline.iss` == `tauri.conf.json` == extension `manifest.json`
- [ ] Publisher **AndalusGames**; `LicenseFile=LICENSE.txt` in Inno
- [ ] `python -m pytest -q` green
- [ ] `scripts/pack_extension.ps1` → `release/Deskline-Extension-*.zip`
- [ ] `scripts/prepare_release.ps1` (or build_installer) → `release/DesklineSetup-<ver>.exe` + `SHA256SUMS.txt`
- [ ] Code-sign Setup + exe per [SIGNING.md](SIGNING.md)
- [ ] GitHub Release on **MiLadaPv/Deskline** with Setup + extension zip + checksums
- [ ] `/welcome` download CTA → releases/latest
- [ ] Install on clean Windows VM → Start Menu → tray → dashboard
- [ ] Uninstall removes Start Menu shortcut; autostart Run key cleared if enabled
- [ ] SmartScreen: no unexplained block after signing + reputation

## License / payment

- [ ] Lemon Squeezy products: Pro Annual, Pro Lifetime, **Team** — [LEMON_SQUEEZY.md](LEMON_SQUEEZY.md)
- [ ] `DESKLINE_LEMON_API_KEY` + checkout URLs (annual / lifetime / team) on release machine
- [ ] Real keys activate; deactivate restores Free (if trial ended)
- [ ] Offline grace: still Pro/Team within 14 days of last validation; Free after

## Chrome Web Store

- [ ] Listing copy from [CHROME_WEB_STORE.md](CHROME_WEB_STORE.md)
- [ ] Privacy policy URL = GitHub `docs/PRIVACY_POLICY.md`
- [ ] Zip uploaded; review submitted

## Privacy pitch

- [ ] Support email responds: milanochka.llc@gmail.com
- [ ] FAQ “not a keylogger” on `/welcome`
- [ ] Activity data never uploaded; only license checks

## Smoke commands

```bat
python -m pytest -q
powershell -ExecutionPolicy Bypass -File scripts\pack_extension.ps1
powershell -ExecutionPolicy Bypass -File scripts\sync_and_restart.ps1
curl http://127.0.0.1:8787/api/license/status
curl http://127.0.0.1:8787/welcome
curl http://127.0.0.1:8787/docs/compare
```
