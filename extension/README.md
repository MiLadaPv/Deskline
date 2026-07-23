# Deskline Browser Extension (Chrome MV3)

Lightweight browser-only tracker. Use it as the trial entry; upgrade to **Deskline Desktop** for full Windows app tracking, screenshots, and system tray.

## Install (unpacked)

1. Open Chrome → `chrome://extensions`
2. Enable **Developer mode**
3. **Load unpacked** → select this `extension/` folder
4. Pin the Deskline icon

## Behavior

- Tracks the active tab (host + title) while Recording
- Stores time locally in `chrome.storage`
- If Deskline Desktop is running on `http://127.0.0.1:8787`, closed segments are posted to `/api/extension/event`
- Popup CTA: **Download Desktop** when the desktop API is offline, or **Open dashboard** when online

## Not included

- OS-wide app tracking (Desktop only)
- Screenshots / tray (Desktop only)
- Cloud sync

## Package for buyers

Zip this folder as `Deskline-Extension-0.4.0.zip` (Chrome Web Store listing can come later).
