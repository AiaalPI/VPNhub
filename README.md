# VPNHub — Telegram VPN Bot

VPNHub is a production Telegram bot that provisions and manages VPN access for users. It is designed to run in containers using Docker Compose and uses PostgreSQL, NATS (JetStream), and Alembic for database migrations. Handlers are intentionally thin; business logic lives in `bot/bot/service`.

Quick overview
- Application entry: `bot/run.py`
- Telegram handlers: `bot/bot/handlers` (thin layer)
- Business logic / services: `bot/bot/service`
- Database models & access: `bot/bot/database`
- NATS configuration & tooling: `bot/nats`

Stack
- Python 3.11+ (see `bot/requirements.txt`)
- PostgreSQL
- NATS (JetStream)
- Docker & Docker Compose
- Alembic for migrations

Getting started
1. Create an `.env` file with the required environment variables (do NOT commit `.env`).
2. Start services with Docker Compose:

```bash
docker-compose up -d
```

3. Run the bot

```bash
# inside the container or a service shell
docker-compose exec bot bash -lc "python run.py"

# or locally (with env vars loaded)
python bot/run.py
```

Database migrations
- Migrations are managed by Alembic. `bot/run.py` runs `alembic upgrade head` automatically when starting. To create a migration run:

```bash
python bot/run.py --newmigrate "migration message"
```

Notes and golden rules
- Do NOT modify `.env` in the repository.
- Do NOT change `docker-compose.yml` unless explicitly required and approved.
- Keep handlers in `bot/bot/handlers` thin — move business logic to `bot/bot/service`.
- Document any behavioral change in `docs/` and `CHANGELOG.md`.

Where to look next
- Configuration loader: `bot/bot/misc/util.py`
- DB engine: `bot/bot/database/main.py`
- Entry point and migration helpers: `bot/run.py`
