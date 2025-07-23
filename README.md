# slackdump (GUI)

Dockerized Flask app to **select Slack channels**, **sync messages into Postgres**, and **browse/search** the DB.

## Quick start

```bash
unzip slackdump_gui.zip
cd slackdump_gui
# edit docker-compose.yml and set SLACK_TOKEN
docker compose up --build
```

Open: http://localhost:8080

### ENV (in `docker-compose.yml`)

- `SLACK_TOKEN` — Bot/User token with scopes:
  - `channels:read`, `groups:read`, `channels:history`, `groups:history`, `users:read`, `reactions:read`
- `SLACK_TYPES` — default: public_channel,private_channel
- `FETCH_THREADS` — true/false
- `OLDEST_TS`, `LATEST_TS` — optional Slack timestamps (string) to bound history

### Re-run sync

Just go to **Sync** in the UI and run again.

### DB schema
Same as the CLI version:
- channels, users, messages, reactions

Generated 2025-07-23T08:15:32.432642
