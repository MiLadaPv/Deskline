# Lemon Squeezy setup (AndalusGames)

Deskline keeps **activity data local**. The only cloud call for monetization is
**license activate/validate** against Lemon Squeezy (Merchant of Record).

## Products to create

1. **Deskline Pro Annual** — subscription, enable License Keys
2. **Deskline Pro Lifetime** — one-time, enable License Keys
3. (Later) **Deskline Team** — per-seat, separate SKU

Copy each product’s checkout URL into environment variables on the build/release machine
or hosting that injects env for the desktop process:

```bat
set DESKLINE_LEMON_API_KEY=...
set DESKLINE_CHECKOUT_URL_ANNUAL=https://....lemonsqueezy.com/checkout/buy/...
set DESKLINE_CHECKOUT_URL_LIFETIME=https://....lemonsqueezy.com/checkout/buy/...
```

Optional:

```bat
set DESKLINE_LICENSE_HMAC_SECRET=long-random-string
set DESKLINE_LICENSE_DEV=0
```

## App flow

1. User pays on Lemon Squeezy checkout (opened from Settings / `/welcome#pricing`).
2. LS emails a **license key**.
3. User pastes key in Deskline → `POST /api/license/activate`.
4. App stores signed `%LOCALAPPDATA%\Deskline\license.json`.
5. Offline grace: 14 days after `last_validated_at`.

## Dev keys (tests / demos)

When `DESKLINE_LEMON_API_KEY` is unset **or** `DESKLINE_LICENSE_DEV=1`:

| Key | Tier |
|-----|------|
| `DESKLINE-PRO-DEV` | Pro |
| `DESKLINE-PRO-LIFE-DEV` | Pro |
| `DESKLINE-TEAM-DEV` | Team (hub) |

Never ship production builds with `DESKLINE_LICENSE_DEV=1`.

## Webhooks (optional later)

For seat management / refunds, add a small license-status API and LS webhooks.
v0.5 uses License API activate from the client, which is enough for solo Pro.
