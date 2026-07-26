# Deskline GTM — 90 days

**Positioning:** Time Doctor–style focus tracking — data stays on your PC.

**ICP:** Solo freelancers and team leads (1–10) on Windows who want focus% without a surveillance/cloud mandate.

**Not ICP:** Enterprises needing DLP, live screen video, or keylogging (Kickidler / StaffCop territory).

## Funnel

```
Chrome Web Store / extension zip
        ↓
  “Get Desktop” CTA
        ↓
 Windows Setup (GitHub Release)
        ↓
  Free + 14-day Pro trial
        ↓
   Pro key  or  Team key (LAN hub)
```

## Channels (priority order)

1. **Chrome Web Store** — lowest friction trial ([CHROME_WEB_STORE.md](CHROME_WEB_STORE.md))
2. **GitHub Releases** — signed Setup + SHA256 ([SIGNING.md](SIGNING.md), [RELEASE_NOTES.template.md](RELEASE_NOTES.template.md))
3. **Product Hunt / Hacker News** — one EN launch when Setup is signed
4. **RU** — VC / Telegram channels on remote work + privacy (1–2 posts)
5. **Comparisons SEO** — `/docs/compare` and [comparisons/](comparisons/)

## Anti-positioning (say this out loud)

| They think we are… | We are… |
|--------------------|---------|
| Another cloud spy | Local-first; activity on disk |
| Kickidler lite | No video wall / DLP |
| Toggl clone | Automatic window focus, not manual timers |

## KPI (weekly)

| Metric | Where |
|--------|--------|
| Extension installs | Chrome dashboard |
| Setup downloads | GitHub Release insights |
| First-run / trial | `%LOCALAPPDATA%\Deskline\funnel.jsonl` via `/api/funnel` |
| Pro / Team activates | Lemon + local license |

## 90-day checklist

### Days 1–30 — Distribution
- [x] Extension pack script + privacy links
- [x] Store listing doc
- [ ] Submit Chrome Web Store (human + $5 fee)
- [x] LicenseFile + GitHub URL hygiene
- [x] prepare_release.ps1 + draft GH workflow
- [ ] OV/EV cert + signed Setup (out of band)
- [x] Welcome download + compare + Team pricing

### Days 31–60 — Team SKU
- [x] Team checkout URL in entitlements
- [x] Lemon docs for Team product
- [ ] Create live Lemon Team product + map tier=team
- [x] Settings copy: Team is available now
- [ ] Smoke 2 PCs on LAN with `DESKLINE-TEAM-DEV`

### Days 61–90 — Growth
- [x] Comparison page + markdown set
- [x] Launch checklist
- [ ] PH / HN / RU posts
- [ ] Weekly funnel review

## Owner notes

Signing certificates, Lemon live products, and store submission require human accounts — repo ships the artifacts and copy.
