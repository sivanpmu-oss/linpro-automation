# LIN PRO Automation

Cloud-hosted automation for Sivan Linor's social media + purchase tracking, running on GitHub Actions.

## What runs here

| Workflow | When | What |
|---|---|---|
| Daily Linpro Post Publisher | 22:00 Israel daily | Publishes today's scheduled English post to @linpro.code |
| Daily Post Verification | 23:30 Israel daily | Emails Sivan a status report + Facebook upload reminder |
| Hourly Purchase Sync to Meta | Every hour | Reads new Cardcom purchase emails, sends Purchase events to Meta CAPI |

## Required secrets (set in GitHub repo Settings → Secrets and variables → Actions)

- `META_ACCESS_TOKEN` — long-lived Meta Graph API token
- `GMAIL_USER` — sivanpmu@gmail.com
- `GMAIL_APP_PASSWORD` — Gmail app password (16 chars)

## State files (auto-committed by workflows)

- `published_log.json` — record of which posts already went up
- `synced_purchases.json` — record of which Cardcom transactions already sent to Meta

## Token expiry

Meta token expires every 60 days. Refresh via Graph API Explorer and update the `META_ACCESS_TOKEN` secret.
