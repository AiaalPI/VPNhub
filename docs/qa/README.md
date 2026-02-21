# QA Scripts

## Available scripts

- `scripts/qa/check_callbacks.py`
  - Static audit: detects literal Telegram `callback_data` values used in keyboards but missing a literal `callback_query` handler.

## Quick run

```bash
python3 scripts/qa/check_callbacks.py --root bot/bot
```

## JSON output

```bash
python3 scripts/qa/check_callbacks.py --root bot/bot --json
```

See detailed documentation: `docs/qa/callback_audit.md`.
