# Deskline — sale one-pager

## Problem

Teams and freelancers lose hours to context-switching and “busy but not focused” days. Most trackers push data to the cloud and feel invasive.

## Product

**Deskline** is a local-first productivity tracker for Windows.

1. **Chrome extension (trial entry)** — track browser focus in minutes; no install friction beyond “Load unpacked” / Web Store later.
2. **Desktop app (full product)** — native Windows window (Tauri) + Python tracker: all apps, optional screenshots, tray Recording/Paused, local dashboard.

Data stays on the PC (`%LOCALAPPDATA%\Deskline`). No required cloud, no keylogging, no stealth agent.

## Why this sells

| Buyer question | Answer |
| --- | --- |
| How do users try it fast? | Chrome extension |
| What’s the upsell? | Desktop: apps + screenshots + tray |
| Privacy / compliance story? | Local-first; optional cloud later |
| What ships today? | Windows installer + extension zip |

## Funnel (Time Doctor–style, privacy-first)

```
Chrome extension  →  “Download Desktop” CTA  →  full Windows app
     (browser)              (upsell)              (apps + screenshots)
```

Cloud multi-user sync is a **post-sale / investment** option — not required for MVP value.

## Buyer artifacts

| Artifact | Path / how to build |
| --- | --- |
| Windows Setup | `build_installer.bat` → `release\DesklineSetup-*.exe` (includes `deskline-desktop.exe` + backend) |
| Script install (dev) | `install.bat` (requires built Tauri shell) |
| Extension zip | Zip the `extension/` folder → `Deskline-Extension-0.4.0.zip` |
| Pitch | This file |

## Boundaries (by design)

- No keylogging / clipboard / mic capture
- No hidden persistence beyond optional user autostart
- No mandatory remote sync in v1
