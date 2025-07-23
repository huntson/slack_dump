# slackdump

Simple Dockerized Python app to pull Slack channel history into a Postgres DB.

## Quick start

1. Put your Slack Bot/User token into `docker-compose.yml` under `SLACK_TOKEN:`
   - The app needs scopes to read channels and history (`channels:read`, `groups:read`, `channels:history`, `groups:history`, `users:read`, `reactions:read` at a minimum).
   - If you need private channels, install the bot in those channels.

2. Optionally edit `SLACK_CHANNELS`:
   - `*` = all visible channels
   - Comma separated list of channel **names** or **ids**

3. Bring it up:

```bash
docker compose up --build
```

The app will run once, ingest data, then exit. Postgres data is persisted in the `pgdata` volume.

Re-run any time you want to sync again:

```bash
docker compose run --rm app
```

## Tables

- `channels` — Slack channels (public/private)
- `users` — Slack users
- `messages` — All messages (including threads)
- `reactions` — Message reactions (one row per user/react)

## Extending

- Add file downloads, attachments, etc. in `main.py` (see Slack `files.*` endpoints).
- Add a scheduler (cron, supercronic) if you want periodic syncs.
- Swap Postgres with anything else supported by SQLAlchemy.

Generated: 2025-07-23T08:09:37.984726
