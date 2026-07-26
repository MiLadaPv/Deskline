# Lemon Squeezy setup (AndalusGames)

Deskline keeps **activity data local**. The only cloud call for monetization is
**license activate/validate** against Lemon Squeezy (Merchant of Record).

## Products to create

1. **Deskline Pro Annual** — subscription, enable License Keys  
2. **Deskline Pro Lifetime** — one-time, enable License Keys  
3. **Deskline Team** — license keys with variant/metadata `tier=team` (or product name containing “team”) so `license_client` maps to Team  

Copy checkout URLs into environment variables on the release machine:

```bat
set DESKLINE_LEMON_API_KEY=...
set DESKLINE_CHECKOUT_URL_ANNUAL=https://....lemonsqueezy.com/checkout/buy/...
set DESKLINE_CHECKOUT_URL_LIFETIME=https://....lemonsqueezy.com/checkout/buy/...
set DESKLINE_CHECKOUT_URL_TEAM=https://....lemonsqueezy.com/checkout/buy/...
```

Optional:

```bat
set DESKLINE_LICENSE_HMAC_SECRET=long-random-string
set DESKLINE_LICENSE_DEV=0
```

## What each tier unlocks

| Tier | History | Screenshots | Export | Company LAN hub |
|------|---------|-------------|--------|-----------------|
| Free | 14 days | No | No | No |
| Pro trial (14d) | Unlimited | Yes | Yes | No |
| Pro | Unlimited | Yes | Yes | No |
| Team | Unlimited | Yes | Yes | **Yes** |

## App flow

1. User pays on Lemon Squeezy checkout (Settings / `/welcome#pricing`).
2. LS emails a **license key**.
3. User pastes key in Deskline → `POST /api/license/activate`.
4. App stores signed `%LOCALAPPDATA%\Deskline\license.json`.
5. Offline grace: 14 days after `last_validated_at`.

## Team LAN hub

1. Activate Team key on the **hub** PC → enable Company mode in Settings.  
2. Create employees / ingest tokens.  
3. On agent PCs set `hub_url` + `hub_ingest_token` (same LAN).  
4. Sessions push to hub; team summary stays on the hub machine — no mandatory activity cloud.

## Dev keys (tests / demos)

When `DESKLINE_LEMON_API_KEY` is unset **or** `DESKLINE_LICENSE_DEV=1`:

| Key | Tier |
|-----|------|
| `DESKLINE-PRO-DEV` | Pro |
| `DESKLINE-PRO-LIFE-DEV` | Pro |
| `DESKLINE-TEAM-DEV` | Team (hub) |

Never ship production builds with `DESKLINE_LICENSE_DEV=1`.

## Webhooks (optional later)

For seat management / refunds, add LS webhooks.  
v0.5.x uses License API activate from the client for solo Pro and Team keys.
