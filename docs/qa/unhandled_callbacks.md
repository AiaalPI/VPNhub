# Unhandled Callbacks

Detected from inline keyboards (`bot/bot/keyboards/inline/*`) against callback handlers (`bot/bot/handlers/*`).

## Current Status

- Last verified: `python3 scripts/qa/check_callbacks.py --root bot/bot` on 2026-03-18
- Result: **0 missing literal callback handlers**
- Current QA script also understands the project patterns `F.data.in_('literal')` and `F.data.startswith('prefix')`, so the previous false positives for help/language/admin dashboard callbacks are resolved.

## Warn-Only Items

The following callbacks are still worth manual review because they are handled but not currently produced by literal inline keyboard payloads:

- `back_choose_locations`
- `free_vpn_connect_btn`
- `none_protocol`
- `promokod_btn`

Notes:
- `back_choose_locations` is an active admin callback in a dynamic static-user flow.
- `free_vpn_connect_btn` is an intentional feature-flagged flow guarded by `IsWorkFreeVPN()` / `FREE_SERVER`.
- `promokod_btn` is intentionally hidden for possible future reuse.

These are not treated as failures by QA. They are candidates for future flow cleanup, hidden-flow review, or dead-code review.
