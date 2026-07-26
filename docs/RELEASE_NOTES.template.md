# Deskline vX.Y.Z

Time Doctor–style focus tracking — **data stays on your PC**.

## Downloads

| File | Notes |
|------|--------|
| `DesklineSetup-X.Y.Z.exe` | Windows installer (sign before public link) |
| `Deskline-Extension-X.Y.Z.zip` | Chrome MV3 (or install from Web Store when live) |
| `SHA256SUMS.txt` | Checksums |

## Install

1. Run the Setup exe (SmartScreen may warn until reputation builds).
2. Optional: load the extension or install from Chrome Web Store.
3. Open dashboard at http://127.0.0.1:8787 — Free / 14-day Pro trial.

## Plans

- **Free** — focus tracking, 14-day history, 3 projects  
- **Pro** — unlimited history, screenshots, export  
- **Team** — Pro + LAN company hub  

Privacy: [PRIVACY_POLICY.md](PRIVACY_POLICY.md)  
Support: milanochka.llc@gmail.com  

## Verify

```bat
certutil -hashfile DesklineSetup-X.Y.Z.exe SHA256
```
