# Duplicates and Unreachable UX Routes

Last reviewed against current code: 2026-03-18.

## Duplicate Callback Handlers

Potential duplicates (same semantic action handled by multiple filters or aliases):

| callback/action | handlers | evidence | risk |
|---|---|---|---|
| Main menu recovery | `back_general_menu_btn` (canonical), legacy alias `answer_back_general_menu_btn` | shared compatibility handler in `bot/bot/handlers/user/main.py` | P4: low compatibility-only complexity |
| Noisy compatibility aliases | `none_protocol` plus legacy `none protocol` | shared fallback handler in `bot/bot/handlers/user/main.py` | P4: low, backward-compatibility only |

## Callback Contract Notes

- Active inline keyboards now emit static literal callback payloads for user flows; text-localized callback variants are no longer part of the live contract.
- Mailing buttons keep localized labels, but their callback payloads stay stable. In particular, mailing key `general_menu_btn` maps to canonical callback `back_general_menu_btn`.

## Unreachable / Dead UX Functions

| function/screen | evidence | assessment |
|---|---|---|
| `show_start_message_new_user` | removed on 2026-03-18 after confirming current `/start` flow issues trial directly | Closed |
| `connect_menu` keyboard builder | removed on 2026-03-18 after confirming no active producers remained | Closed |
| `trial_pay_button` keyboard builder | removed on 2026-03-18 after confirming no active entry from current user path | Closed |

## Fallback Router Behavior (Catch-all)

- Catch-all message handler: `bot/bot/handlers/other/main.py:23` (`@other_router.message()`)
- Current behavior: active FSM is now guarded; the catch-all returns a contextual hint instead of resetting the flow.
- Remaining risk: outside FSM, unmatched messages still bounce to the main menu, which may hide narrow text-command regressions.
