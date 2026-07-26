# Chrome Web Store listing — Deskline extension

Public privacy policy (HTTPS):  
https://github.com/MiLadaPv/Deskline/blob/master/docs/PRIVACY_POLICY.md

Homepage:  
https://github.com/MiLadaPv/Deskline

Support email: milanochka.llc@gmail.com

## Package

```powershell
powershell -ExecutionPolicy Bypass -File scripts\pack_extension.ps1
```

Upload `release/Deskline-Extension-<version>.zip` in the [Chrome Developer Dashboard](https://chrome.google.com/webstore/devconsole).

## Store listing (English)

**Name:** Deskline

**Short description (≤132 chars):**  
Track browser focus locally. Pair with Deskline Desktop for full Windows app tracking — no cloud activity sync.

**Detailed description:**

```
Deskline is a privacy-first focus tracker.

The Chrome extension measures time on the active tab and stores it locally.
When Deskline Desktop is running on your PC (http://127.0.0.1:8787), tab
segments sync to the local dashboard — never to a mandatory activity cloud.

Desktop adds Windows app tracking, optional screenshots (Pro), tray controls,
and Free/Pro/Team plans. Activity stays under %LOCALAPPDATA%\Deskline.

Not a keylogger. No clipboard or microphone access.
Host permission is limited to localhost so the extension can reach Desktop.

Download Desktop: https://github.com/MiLadaPv/Deskline/releases/latest
Privacy: https://github.com/MiLadaPv/Deskline/blob/master/docs/PRIVACY_POLICY.md
```

**Category:** Productivity

**Language:** English (+ Russian screenshots optional)

## Permissions justification

| Permission | Why |
|------------|-----|
| `storage` | Local focus totals / pause state |
| `tabs` | Active tab host + title for focus segments |
| `alarms` | Periodic flush while Recording |
| Host `127.0.0.1:8787` / `localhost:8787` | Optional sync to Deskline Desktop API |

## Screenshots to prepare (1280×800 or 640×400)

1. Popup showing today’s browser time  
2. Desktop dashboard “картина дня” (paired)  
3. Welcome/pricing privacy message  

## Submission checklist

- [ ] Zip built from current `manifest.json` version  
- [ ] Privacy policy URL reachable without login  
- [ ] Single purpose description matches permissions  
- [ ] No remote code  
- [ ] Submit for review  

Developer registration fee (~$5 one-time) is out of band.
