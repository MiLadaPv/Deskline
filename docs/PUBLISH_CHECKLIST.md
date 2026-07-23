# Deskline publish double-check (v0.5.0)

Use this before any public download link goes live.

## Product / freemium

- [ ] Fresh install shows onboarding once
- [ ] First 14 days: Pro trial (screenshots + export + unlimited history)
- [ ] After trial without key: Free limits (14d history, 3 projects, no screenshots)
- [ ] Activate `DESKLINE-PRO-DEV` only on dev builds; production uses Lemon Squeezy key
- [ ] Company hub returns 402 Team on Free/Pro
- [ ] Paywall modal appears on gated actions
- [ ] `/welcome#pricing` lists Free vs Pro
- [ ] Privacy/Terms no longer say “Legal draft”

## Distribution

- [ ] `__version__` == `pyproject.toml` == `installer/deskline.iss` == `tauri.conf.json` (**0.5.0**)
- [ ] Publisher **AndalusGames**; LicenseFile present in Inno
- [ ] `python -m pytest -q` green
- [ ] `scripts/build_installer.ps1` produces `release/DesklineSetup-0.5.0.exe`
- [ ] Code-sign Setup + exe per [SIGNING.md](SIGNING.md)
- [ ] Upload GitHub Release with SHA256
- [ ] Install on clean Windows VM → Start Menu → tray → dashboard
- [ ] Uninstall removes Start Menu shortcut; autostart Run key cleared if enabled
- [ ] SmartScreen: no unexplained block after signing + reputation

## License / payment

- [ ] Lemon Squeezy products created (Annual + Lifetime) — [LEMON_SQUEEZY.md](LEMON_SQUEEZY.md)
- [ ] `DESKLINE_LEMON_API_KEY` + checkout URLs set on release machine
- [ ] Real key activates; deactivate restores Free (if trial ended)
- [ ] Offline grace: still Pro within 14 days of last validation; Free after

## Privacy pitch

- [ ] Support email responds: milanochka.llc@gmail.com
- [ ] FAQ “not a keylogger” on `/welcome`
- [ ] Activity data never uploaded; only license checks

## Smoke commands

```bat
python -m pytest -q
powershell -ExecutionPolicy Bypass -File scripts\sync_and_restart.ps1
curl http://127.0.0.1:8787/api/license/status
curl http://127.0.0.1:8787/welcome
```
