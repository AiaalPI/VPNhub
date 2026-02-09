# Architecture

This document summarizes the high-level components and runtime flows of VPNHub.

Components
- `bot/` — main Python application package.
- `bot/bot/handlers` — Telegram handlers. These should contain only thin logic to validate and parse updates, delegating real work to services.
- `bot/bot/service` — Business logic: creating keys, billing, user flows, server control.
- `bot/bot/database` — SQLAlchemy models, DB engine configuration, and helper methods.
- `bot/nats` — NATS (JetStream) configuration and helper scripts. NATS is used for background tasks and coordination (e.g., key removal).
- `bot/run.py` — process entrypoint. Runs Alembic migrations on startup and starts the bot.
- Alembic — DB migrations under `bot/bot/alembic` and `bot/bot/alembic/versions`.

Primary request flow
1. Telegram receives an update and sends it to the bot.
2. A handler in `bot/bot/handlers` parses the update and delegates to a function in `bot/bot/service`.
3. Service code performs business logic: database reads/writes via `bot/bot/database`, calls external payments or crypto APIs, and may publish/consume messages on NATS for asynchronous tasks.

Background jobs & async flows
- NATS consumers: job consumers subscribe to JetStream streams to process tasks such as key removal, synchronizing expirations, or other long-running jobs.
- `bot/bot/misc/start_consumers.py` and NATS helpers initialize and manage consumer lifecycle.
- Periodic/background tasks are implemented as services and triggered via NATS messages or internal loops.

Database & migrations
- The project uses SQLAlchemy with asyncpg in production and sqlite in debug mode.
- `bot/run.py` runs `alembic upgrade head` on startup; developers can create migrations with `python bot/run.py --newmigrate "desc"`.

Logging & observability
- Logging configured in `bot/run.py` using rotating file handlers writing to `logs/all.log` and `logs/errors.log`.
- NATS exposes a simple HTTP endpoint (port 8222) for health/metrics when running the containerized NATS.

Deployment notes
- Docker Compose is the primary deployment descriptor: `docker-compose.yml` wires up `postgres`, `nats`, `bot` and other services.
- Inside Compose the Postgres host is `postgres_db_container` and NATS accessible at `nats:4222`.
