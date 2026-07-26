# Deskline — sale / GTM one-pager

## Problem

Teams and freelancers lose hours to context-switching and “busy but not focused” days. Most trackers push activity to the cloud and feel invasive — or they are full surveillance suites.

## Product

**Deskline** is a local-first productivity tracker for Windows.

**One line:** Time Doctor–style focus tracking — data stays on your PC.

1. **Chrome extension (trial entry)** — browser focus in minutes; Chrome Web Store or zip.
2. **Desktop app (full product)** — native Windows window (Tauri) + Python tracker: all apps, optional screenshots, tray Recording/Paused, local dashboard.
3. **Team (LAN hub)** — one hub PC + agent ingest tokens; still no mandatory activity cloud.

## ICP

- Freelancers / makers / small leads (1–10) on Windows  
- Care about focus% and privacy  
- Not shopping for DLP or live screen video  

## Why this sells

| Buyer question | Answer |
| --- | --- |
| How do users try it fast? | Chrome extension |
| What’s the upsell? | Desktop: apps + screenshots + tray |
| Privacy / compliance story? | Local-first; license check only |
| Team without SaaS? | LAN hub (Team tier) |
| What ships today? | Windows installer + extension zip |

## Funnel

```
Chrome extension  →  “Download Desktop” CTA  →  full Windows app  →  Pro / Team
     (browser)              (upsell)              (apps + screenshots)   (key)
```

## Anti-positioning

- **Not** Kickidler / StaffCop — no video wall, no keylogger  
- **Not** Toggl-only — automatic focus, not manual timers  
- **Not** mandatory Time Doctor cloud — same idea, local data  

## Buyer artifacts

| Artifact | Path / how to build |
| --- | --- |
| Windows Setup | `scripts/prepare_release.ps1` → `release/DesklineSetup-*.exe` (then sign) |
| Extension zip | `scripts/pack_extension.ps1` |
| Store listing | [CHROME_WEB_STORE.md](CHROME_WEB_STORE.md) |
| 90-day GTM | [GTM_90.md](GTM_90.md) |

## Boundaries (by design)

- No keylogging / clipboard / mic capture  
- No hidden persistence beyond optional user autostart  
- No mandatory remote activity sync  
- Windows-first for this horizon (Mac later, not abandoned forever)
