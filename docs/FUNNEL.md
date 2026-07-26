# Local funnel metrics

Events append to `%LOCALAPPDATA%\Deskline\funnel.jsonl` (no cloud).

## Events

| Event | When |
|-------|------|
| `welcome_view` | GET `/welcome` |
| `pro_activate` / `team_activate` | Successful license activate |
| `app_first_open`, `trial_start`, `download_click`, `extension_paired` | Via `POST /api/funnel` |

## API

```http
POST /api/funnel
{"event":"download_click","meta":{"src":"welcome"}}

GET /api/funnel?limit=50
```

Review weekly with [GTM_90.md](GTM_90.md) and [LAUNCH_CHECKLIST.md](LAUNCH_CHECKLIST.md).
