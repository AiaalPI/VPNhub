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
- **Status: ✅ Already fixed** — `back_menu_button(lang)` is passed on all three FSM prompts (`referral_user.py:187`, `213`, `219`, `234`).
- Location: `bot/bot/handlers/user/referral_user.py:188`, `213`, `225`.

5) **Support flow reuses `WithdrawalFunds` state group** — 🔲 TODO
- Location: `bot/bot/handlers/user/referral_user.py:49`, `350`, `367`, `386`, `404`, `420`.
- Why: `input_message_admin` state (used for support messages to admin) lives inside `WithdrawalFunds`; state collision risk if user is mid-withdrawal and triggers support.
- Minimal fix: create `SupportState(StatesGroup)` with one `input_message_admin` state; update three `set_state` calls and the `@router.message(WithdrawalFunds.input_message_admin)` handler.

6) **Fallback router can override intent for unmatched messages** — 🔲 TODO
- Location: `bot/bot/handlers/other/main.py:23`.
- Why: any unmatched user text gets main-menu photo, potentially interrupting contextual typing tasks.
- Minimal fix: ignore fallback when `FSMContext` has active state; reply with contextual hint instead.

7) **UX clutter due mixed `answer_photo` vs `edit_message`** — 🔲 TODO
- Location examples: `bot/bot/handlers/user/main.py:191`, `235`, `529`; `keys_user.py:94`; `referral_user.py:151`.
- Why: stack of repeated media messages makes navigation harder and hides latest actionable screen.
- Minimal fix: standardize per flow (prefer edit for callback-driven navigation).

## P2 Findings

8) **Duplicate callback handlers for text-localized data that callback UI never sends** — 🔲 TODO
- Location examples: `bot/bot/handlers/user/main.py:469`, `522`; `keys_user.py:83`; `referral_user.py:79`, `124`; `payment_user.py:281`.
- Why: callback data from inline keyboard is static (`vpn_connect_btn`, etc.), not translated label text; duplicates add noise/risk.
- Minimal fix: keep only literal callback-data handlers for callback queries.

9) **Dead/legacy screen function not used** — 🔲 TODO
- Location: `bot/bot/handlers/user/main.py:246` (`show_start_message_new_user`).
- Why: unused UX branch diverges from actual flow and confuses maintenance.
- Minimal fix: remove or document as intentional future path.

10) **Dead callback route `general_menu`** — 🔲 TODO
- Location: `bot/bot/handlers/user/main.py:261`.
- Why: extra route without discoverable trigger; no keyboard sends this callback.
- Minimal fix: remove route or wire it from keyboard explicitly.

11) **Language mismatch in some EN microcopy quality** — 🔲 TODO
- Location examples: `bot/bot/locale/en/LC_MESSAGES/bot.po` (`not_server_free_vpn` contains typo/escape artifact).
- Why: trust and readability issues in conversion-critical flow.
- Minimal fix: copy edit EN strings for core purchase/connect screens first.

12) **Main-menu recovery callback split across multiple equivalents** — 🔲 TODO
- Location: `bot/bot/handlers/user/main.py:183`, `212`, `227`.
- Why: multiple aliases (`general_menu_btn`, `back_general_menu_btn`, `answer_back_general_menu_btn`) complicate instrumentation and predictability.
- Minimal fix: standardize to one callback for "Main menu" and keep alias compatibility temporarily.

## Notes on Instrumentation Quality
- Positive: route and update logging is already sufficient to trace `handled` status and handler path:
  - `bot/bot/middlewares/update_logging.py:40` (`update.in/out handled`)
  - `bot/bot/middlewares/update_logging.py:75` (`route.enter/exit`).
