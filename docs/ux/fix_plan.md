# UX Fix Plan (Prioritized, Minimal Change)

## Goal
Reduce flow breaks/confusion without changing core business behavior (payments, provisioning, referral logic remain intact).

## Priority 0 (Do first)

1) Fix EN empty key-action labels
- Files: `bot/bot/locale/en/LC_MESSAGES/bot.po`.
- Change: set `user_key_get`, `user_key_extend`, `user_key_edit` msgstr values.
- Impact: restores key-management actions for EN users.

2) Add handler for `callback_data='none'`
- Files: user callback router (recommended `bot/bot/handlers/user/main.py` or `payment_user.py`).
- Change: alert with clear reason (e.g., "Action unavailable right now").
- Impact: removes silent dead taps in payment/referral widgets.

## Priority 1 (Conversion + navigation)

3) Normalize user back-labels
- Files: `bot/bot/keyboards/inline/user_inline.py` (`choose_type_vpn`, `renew`).
- Change: replace `admin_back_admin_menu_btn` label key with user-facing key.
- Impact: less confusion in checkout/connect path.

4) Add recovery keyboard in text FSM prompts
- Files: `bot/bot/handlers/user/referral_user.py` (withdraw flow prompts).
- Change: include inline `back_general_menu_btn` on each ask-step message.
- Impact: fewer abandoned states.

5) Separate support state from withdrawal state
- Files: `bot/bot/handlers/user/referral_user.py`.
- Change: create `SupportState.input_message_admin`; keep handler logic same.
- Impact: cleaner transitions; lower accidental state collision risk.

## Priority 2 (Consistency and maintainability)

6) Deduplicate callback handlers
- Files: `bot/bot/handlers/user/main.py`, `keys_user.py`, `referral_user.py`, `payment_user.py`.
- Change: keep canonical literal callback handlers; remove text-based callback duplicates.
- Impact: cleaner routing graph and easier debugging.

7) Unify callback-driven rendering strategy
- Files: callback handlers currently mixing `answer_photo` and `edit_message`.
- Change: use `edit_message` for in-thread navigation screens where possible.
- Impact: cleaner chat history; better perceived UX.

8) Guard fallback router during active FSM
- Files: `bot/bot/handlers/other/main.py`.
- Change: if state active, avoid hard-reset to main menu.
- Impact: prevents accidental interruption.

## Suggested Delivery Sequence
1. Locale + `none` handler (safe, fast).
2. Back-label and FSM recovery buttons.
3. State split for support.
4. Handler dedup + fallback guard.
5. Optional visual consistency pass (edit vs answer).

## Validation Checklist
- `/start` new user: welcome + auto-trial + instructions + main menu recovery.
- Existing user: main menu appears once, no duplicate media spam.
- Connect flow: protocol -> location -> tariff/payment path always has back/main menu.
- Referral/support: each step recoverable to main menu.
- Tapping unavailable action (`none`) gives clear alert.
- EN locale key detail buttons visible and actionable.
