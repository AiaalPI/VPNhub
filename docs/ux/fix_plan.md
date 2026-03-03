# UX Fix Plan (Prioritized, Minimal Change)

## Goal
Reduce flow breaks/confusion without changing core business behavior (payments, provisioning, referral logic remain intact).

## Priority 0 (Do first)

1) ~~Fix EN empty key-action labels~~
- **Status: ✅ Already done** — verified 2026-03-02, all strings populated and `.mo` compiled.
- Files: `bot/bot/locale/en/LC_MESSAGES/bot.po`.

2) ~~Add handler for `callback_data='none'`~~
- **Status: ✅ Already done** — `main.py:242`, shows `show_alert=True` popup with localized text.
- Files: `bot/bot/handlers/user/main.py`.

## Priority 1 (Conversion + navigation)

3) ~~Normalize user back-labels~~
- **Status: ✅ Already done** — both locations use `back_general_menu_btn`.
- Files: `bot/bot/keyboards/inline/user_inline.py`.

4) ~~Add recovery keyboard in text FSM prompts~~
- **Status: ✅ Already done** — `back_menu_button(lang)` on all withdraw FSM steps.
- Files: `bot/bot/handlers/user/referral_user.py`.

5) ~~Separate support state from withdrawal state~~
- **Status: ✅ Already done** — `SupportState.input_message_admin` created; 3× `set_state` + handler updated.
- Files: `bot/bot/handlers/user/referral_user.py`.

## Priority 2 (Consistency and maintainability)

6) ~~Deduplicate callback handlers~~
- **Status: ✅ Already done** — removed 8 dead `btn_text()` callback_query handlers (no reply keyboard uses these callback_data values). Kept canonical inline handlers.
- Files: `main.py`, `keys_user.py`, `referral_user.py`, `payment_user.py`.

7) ~~Unify callback-driven rendering strategy~~
- **Status: ✅ Already done** — `answer_back_general_menu_btn` and `general_menu` handlers now use `edit_message` instead of `answer_photo`. Error fallbacks and language-switch (delete+answer) kept as-is.
- Files: `bot/bot/handlers/user/main.py`.

8) ~~Guard fallback router during active FSM~~
- **Status: ✅ Already done** — `handlers/other/main.py:30` checks `state.get_state()` and returns hint instead of resetting to menu.
- Files: `bot/bot/handlers/other/main.py`.

## Suggested Delivery Sequence
1. ~~Locale + `none` handler~~ ✅ done
2. ~~Back-label and FSM recovery buttons~~ ✅ done
3. ~~State split for support~~ ✅ done
4. ~~Fallback guard~~ ✅ done
5. ~~Handler dedup~~ ✅ done
6. ~~Visual consistency pass (edit vs answer)~~ ✅ done

## Validation Checklist
- `/start` new user: welcome + auto-trial + instructions + main menu recovery.
- Existing user: main menu appears once, no duplicate media spam.
- Connect flow: protocol -> location -> tariff/payment path always has back/main menu.
- Referral/support: each step recoverable to main menu.
- Tapping unavailable action (`none`) gives clear alert.
- EN locale key detail buttons visible and actionable.
