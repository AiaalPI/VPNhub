# QA Manual Checklist (RU/EN)

## 1) `/start` new user

- RU: Новый Telegram user без записи в БД -> `/start`.
- EN: New Telegram user with no DB record -> `/start`.
- Verify:
  - Welcome photo `hello_bot.jpg` + welcome text;
  - Trial key issue attempt starts;
  - If no servers: clear `not_server` message;
  - No silent crash in logs.

## 2) `/start` existing user

- Verify main menu photo + menu buttons appear.
- Validate callbacks: `vpn_connect_btn`, `affiliate_btn`, `language_btn`, `help_btn`, `about_vpn_btn`.

## 3) Connect VPN flow

- Path: main menu -> connect -> type -> location -> key output.
- Verify back recovery: `back_general_menu_btn` returns to menu.
- Validate key operations: detail/show/extend/edit callbacks work.

## 4) Buy/Renew flow

- Path: key renew -> month select -> payment provider -> invoice.
- Test promo application path and no-promo path.
- Validate `none` callback alert if no payment providers configured.

## 5) Referral flow

- Path: `affiliate_btn` -> referral screen.
- Verify share link button works.
- If balance below threshold, clicking disabled withdrawal (`none`) shows alert.

## 6) Referral withdrawal FSM

- Path: `withdrawal_of_funds` -> amount -> payment method -> communication.
- Negative tests:
  - non-numeric amount;
  - amount below min;
  - amount greater than balance.
- Ensure user always has visible back/main menu recovery.

## 7) Support flow

- Path: `help_btn` -> support screen -> send message.
- Verify admin receives message and user gets success/fail feedback.

## 8) Language toggle

- Path: `language_btn` -> choose language -> menu refresh.
- Verify changed locale applies on next screens.

## 9) `none` callbacks

- Every button with `callback_data='none'` must show alert and not hang.
- Verify user sees explicit unavailability message.

## 10) Unhandled callback probes (regression guard)

- Manually trigger via test button or raw callback data (if test harness exists):
  - `none protocol`
  - `back_instructions`
  - `back_help_menu`
  - `ChooseTypeVpnHelp(...)`
- Expected AS-IS: currently unhandled (documented defects).

## 11) Fallback catch-all behavior

- Send random text in private chat.
- Expected: menu is shown by `other_router` catch-all.
- Confirm this does not break active FSM or hide actionable errors.

## 12) Logging checks for routing

- Confirm middleware logs for each test:
  - `update.in ...`
  - `route.enter ...`
  - `route.exit ...`
  - `update.out ... handled=...`
