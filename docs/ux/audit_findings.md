# UX Audit Findings (Current Code)

## Severity Legend
- P0: flow break / user stuck / critical action unavailable.
- P1: high confusion or likely drop-off.
- P2: consistency/polish/maintainability UX debt.

## P0 Findings

1) ~~Empty EN labels for key actions (buttons may render blank)~~
- **Status: ✅ Already fixed** — `user_key_get`, `user_key_extend`, `user_key_edit` are populated in `bot.po` and `.mo` is compiled (verified 2026-03-02).
- Location: `bot/bot/locale/en/LC_MESSAGES/bot.po`, used by `bot/bot/keyboards/inline/user_inline.py:710`.

## P1 Findings

2) ~~Placeholder callback `none` has no handler/feedback~~
- **Status: ✅ Already fixed** — handler exists at `bot/bot/handlers/user/main.py:242` (`F.data == 'none'` → `call.answer(text, show_alert=True)`).
- Location: `bot/bot/keyboards/inline/user_inline.py:204`, `205`, `544`.

3) ~~Back label uses admin text key in user flow~~
- **Status: ✅ Already fixed** — both locations (`user_inline.py:299`, `372`) already use `back_general_menu_btn`.
- Location: `bot/bot/keyboards/inline/user_inline.py:299`, `372`.

4) ~~No inline recovery in withdrawal FSM steps~~
- **Status: ✅ No longer applicable** — the withdrawal flow has been removed from the current product surface.
- Location: historical note only; no active withdrawal FSM remains.

5) ~~Support flow reuses `WithdrawalFunds` state group~~
- **Status: ✅ Already fixed** — `SupportState.input_message_admin` is isolated from the removed withdrawal flow and is now the only support input state.

6) ~~Fallback router can override intent for unmatched messages~~
- **Status: ✅ Already fixed** — active FSM state is now guarded and receives a hint instead of reset.

7) **UX clutter due mixed `answer_photo` vs `edit_message`** — 🔲 TODO
- Location examples: `bot/bot/handlers/user/main.py:191`, `235`, `529`; `keys_user.py:94`; `referral_user.py:151`.
- Why: stack of repeated media messages makes navigation harder and hides latest actionable screen.
- Minimal fix: standardize per flow (prefer edit for callback-driven navigation).

## P2 Findings

8) ~~Duplicate callback handlers for text-localized data that callback UI never sends~~
- **Status: ✅ Mostly fixed** — active callback routing now relies on literal/static `callback_data`, and the old noisy callback-text duplicates are no longer present in the current handler set.
- Remaining nuance: a few compatibility aliases still exist for already-sent old messages (`answer_back_general_menu_btn`, legacy `none protocol` callback value), but they are explicit backward-compatibility paths rather than text-localized duplicates.

9) **Dead/legacy screen function not used** — ✅ Fixed
- Current: legacy helper `show_start_message_new_user` removed after confirming current `/start` flow issues trial directly.
- User impact: none expected; maintenance noise reduced.

10) **Dead callback route `general_menu`** — ✅ Fixed
- Current: legacy callback alias removed; no keyboard sends this callback.
- User impact: none expected; routing and analytics are simpler.

11) **Language mismatch in some EN microcopy quality** — 🔲 TODO
- Location examples: `bot/bot/locale/en/LC_MESSAGES/bot.po` (payment, support, and admin-status strings still need ongoing copy polish).
- Why: trust and readability issues in conversion-critical flow.
- Minimal fix: copy edit EN strings for core purchase/connect screens first.

12) **Main-menu recovery callback split across multiple equivalents** — ✅ Mostly fixed
- Current: new keyboards now use `back_general_menu_btn` as the canonical callback.
- Remaining debt: `answer_back_general_menu_btn` is still accepted as a compatibility alias for already-sent messages.
- Minimal next step: remove the alias after enough time has passed for old messages to age out.

## Notes on Instrumentation Quality
- Positive: route and update logging is already sufficient to trace `handled` status and handler path:
  - `bot/bot/middlewares/update_logging.py:40` (`update.in/out handled`)
  - `bot/bot/middlewares/update_logging.py:75` (`route.enter/exit`).
