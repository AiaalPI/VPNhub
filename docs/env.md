# Environment variables

This file lists environment variables used by the project. Do NOT commit secrets or `.env` files.

Core bot configuration (required)
- `TG_TOKEN` — Telegram bot token (required). Used by Telegram API client.
- `ADMIN_TG_ID` — Telegram user id of the bot administrator (required).
- `NAME` — Bot display name (required).
- `LANGUAGES` — Comma-separated languages supported (e.g. `en,ru`).

Feature flags / behavior (required or validated)
- `CHECK_FOLLOW` — `0` or `1`. If `1`, the bot validates channel follow.
- `ID_CHANNEL` — Channel ID to check follow against (required if `CHECK_FOLLOW=1`).
- `LINK_CHANNEL` — Channel invite link (required if `CHECK_FOLLOW=1`).
- `NAME_CHANNEL` — Channel display name (required if `CHECK_FOLLOW=1`).

Pricing / limits (validated)
- `PRICE_SWITCH_LOCATION` — Price for changing key location (int).
- `MONTH_COST` — Comma-separated month prices (e.g. `500,900,1700`).
- `TRIAL_PERIOD` — Trial period in seconds.
- `FREE_SWITCH_LOCATION` — Number of free location switches (int > 0).
- `FREE_SERVER` — `0` or `1` (free VPN servers enabled).
- `LIMIT_GB_FREE` — GB limit for free servers (required when `FREE_SERVER=1`).
- `LIMIT_IP` — Max IPs per user (defaults to 0 when empty).
- `LIMIT_GB` — GB limit per paid plan (defaults to 0 when empty).

Referral / payouts
- `REFERRAL_DAY` — Days per referral window (int).
- `REFERRAL_PERCENT` — Percent paid to referrer (int).
- `MINIMUM_WITHDRAWAL_AMOUNT` — Minimum withdrawal threshold (int).

Payment providers (optional; empty string if unused)
- `YOOMONEY_TOKEN`, `YOOMONEY_WALLET`
- `LAVA_TOKEN_SECRET`, `LAVA_ID_PROJECT`
- `YOOKASSA_SHOP_ID`, `YOOKASSA_SECRET_KEY`
- `CRYPTOMUS_KEY`, `CRYPTOMUS_UUID`
- `HELEKET_KEY`, `HELEKET_UUID`
- `WATA_TOKEN_CARD`, `WATA_TOKEN_SBP`, `WATA_TOKEN_VISA`
- `CRYPTO_BOT_API`

Runtime / infra
- `DEBUG` — `True` or `False`. When `True` the app uses a local sqlite DB and enables debug behaviour.
- `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD` — Postgres credentials used when `DEBUG` is not `True`.
- `PGADMIN_DEFAULT_EMAIL`, `PGADMIN_DEFAULT_PASSWORD` — PGAdmin credentials validated by startup checks.
- `NATS_URL` — (optional) when `DEBUG` is enabled you can override NATS URL. By default NATS address is `nats://nats:4222` inside compose.

Other
- `IMPORT_DB` — `1`/`0` import initial DB dump behaviour.
- `SHOW_DONATE` — `1`/`0` whether to show donate buttons.
- `IS_WORK_EDIT_KEY` — `1`/`0` enable edit key workflow.
- `TG_STARS`, `TG_STARS_DEV` — internal tokens/flags used for stars/dev endpoints.
- `FONT_TEMPLATE` — optional font/template name for generated images.

Notes
- The application will raise an exception at startup if required environment variables are missing or invalid; check logs to see which variable is failing.
- Do not store secrets in VCS. Keep `.env` out of commits.
