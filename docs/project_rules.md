# Project Rules and Conventions

These rules ensure code quality, maintainability, and safe operation in production.

Core rules
- Handlers must be thin: place only request parsing, validation and delegation logic in `bot/bot/handlers`.
- Business logic belongs in `bot/bot/service` or other service modules under `bot/bot`.
- Do not change runtime behaviour without documenting it in `docs/` and `CHANGELOG.md`.
- Do NOT modify `.env` files inside the repository. Do NOT commit secrets.
- Do NOT change `docker-compose.yml` unless explicitly requested and reviewed.

Coding conventions
- Use type hints for public functions and methods.
- Prefer small, focused functions; keep cyclomatic complexity low.
- Raise well-defined exceptions for invalid configuration at startup so missing env vars fail fast.
- Keep imports local in long-running loops or where import-time side effects matter.

Tests & changes
- Add unit tests for new business logic when feasible.
- When changing DB models, create alembic migrations under `bot/bot/alembic/versions` and include a brief description.

Logging & errors
- Use the existing logging setup in `bot/run.py`. Log at appropriate levels (`INFO`, `WARNING`, `ERROR`).
- Do not log secrets or full payment tokens.

Infrastructure
- Use Docker Compose for local and production-like runs. Keep service names and network assumptions in mind (e.g., `postgres_db_container` host).

Documentation
- Add or update documentation in `docs/` for any change that affects deployment, configuration, or behavior.
- Add an entry to `CHANGELOG.md` for notable changes under the appropriate unreleased/released section.
