# Deskline Browser Extension (Chrome MV3)

Lightweight browser-only tracker. Trial entry → upgrade to **Deskline Desktop** for full Windows app tracking.

**Positioning:** Time Doctor–style focus tracking — data stays on your PC.

## Install from Chrome Web Store (preferred)

See [docs/CHROME_WEB_STORE.md](../docs/CHROME_WEB_STORE.md) for listing copy and submission steps.

## Install (unpacked / dev)

1. Open Chrome → `chrome://extensions`
2. Enable **Developer mode**
3. **Load unpacked** → select this `extension/` folder
4. Pin the Deskline icon

## Behavior

- Tracks the active tab (host + title) while Recording
- Stores time locally in `chrome.storage`
- If Deskline Desktop is running on `http://127.0.0.1:8787`, closed segments are posted to `/api/extension/event`
- Popup CTA: **Get Desktop** when offline, or **Open dashboard** when online
- Footer links: Privacy + Support

## Package zip

```powershell
powershell -ExecutionPolicy Bypass -File scripts\pack_extension.ps1
```

Output: `release/Deskline-Extension-<version>.zip` (version from `manifest.json`).

## Not included

- OS-wide app tracking (Desktop only)
- Screenshots / tray (Desktop only)
- Cloud sync / keylogging
