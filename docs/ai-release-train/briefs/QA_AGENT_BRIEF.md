# QA Flow Agent — VPNHub

## Goal
Automatically validate UX routing quality from code (handlers, callbacks, FSM).
Generate documentation only (docs/qa/*). No code changes.

## Scope
- Telegram bot handlers and routers
- inline keyboards / callback_data
- FSM states and transitions (user-facing)
- recovery navigation (Back / Main menu)
- duplicates / unreachable UX routes

## Checks (Must)
1) Callback coverage
- Every inline button callback_data must have at least one handler.
- Handler list must include its file path and line number.
- Any callback_data like "none" is allowed only if there is an explicit handler that shows an alert.

2) Dead-ends
- Detect screens/messages that have no navigation exit (no Back/Main menu) where it should exist.
- Detect callback handlers that only `answer()` without providing next step, if used as a screen transition.

3) FSM recovery
- For each FSM state where user is expected to input text/number:
  - confirm there is a recovery path shown to user (Back/Main menu/cancel)
  - list the exact message(s) where reply_markup is attached
- Identify FSM states that can trap user.

4) Duplicates and unreachable
- Duplicate callback handlers: multiple handlers bound to the same callback_data/filter.
- Unreachable UX functions/screens: functions that are never called by any handler or route.

5) Fallback router behavior
- Identify any "catch-all" message handlers that route users to main menu and may hide errors.
- Document their risk and how to test.

## Output (Required files)
Create docs/qa/ directory and generate:

1) docs/qa/callback_index.md
- Table: callback_data | handler function | file:line | router | notes
- Group by feature: main menu, vpn/connect, subscription, referral, support, language, admin (if present)

2) docs/qa/unhandled_callbacks.md
- List every callback_data referenced in keyboards that has no handler
- Include source file:line where the button is created

3) docs/qa/fsm_recovery.md
- FSM groups and states
- For each state: entry message, expected input, recovery buttons, handler file:line
- Highlight gaps as P0/P1

4) docs/qa/duplicates_unreachable.md
- Duplicate handlers list (same callback_data/filter)
- Unreachable UX functions list (never referenced)
- Include evidence (file:line)

5) docs/qa/test_checklist.md
- Manual test checklist for QA (RU/EN):
  - /start new user
  - /start existing user
  - connect flow
  - buy/renew
  - referral withdraw
  - support
  - language toggle
  - "none" buttons should show alert

## Constraints
- Documentation only; do NOT modify business logic or handlers.
- Use only information derived from current repository.
- Keep output concise and actionable.
