# QA Manual Checklist (RU/EN)

## 1) `/start` new user

- RU: Новый Telegram user без записи в БД -> `/start`.
- EN: New Telegram user with no DB record -> `/start`.
- Verify:
  - Flow goes directly into trial key issue attempt for a truly new user;
  - If no eligible trial server exists: clear `not_server` message;
  - No stale welcome-only screen blocks trial activation;
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

## 6) Support flow

- Path: `help_btn` -> support screen -> send message.
- Verify admin receives message and user gets success/fail feedback.

## 7) Language toggle

- Path: `language_btn` -> choose language -> menu refresh.
- Verify changed locale applies on next screens.

## 8) `none` callbacks

- Every button with `callback_data='none'` must show alert and not hang.
- Verify user sees explicit unavailability message.

## 9) Callback recovery probes (regression guard)

- Manually trigger via test button or raw callback data (if test harness exists):
  - `none_protocol`
  - `back_instructions`
  - `back_help_menu`
  - `ChooseTypeVpnHelp(...)`
- Expected:
  - `none_protocol` shows explicit "no protocols available" feedback and returns safely;
  - `back_instructions` returns to the instruction screen;
  - `back_help_menu` returns to the support/help screen;
  - `ChooseTypeVpnHelp(...)` opens protocol-specific instructions.

## 10) Fallback catch-all behavior

- Send random text in private chat.
- Expected: menu is shown by `other_router` catch-all.
- Confirm this does not break active FSM or hide actionable errors.

## 11) Logging checks for routing

- Confirm middleware logs for each test:
  - `update.in ...`
  - `route.enter ...`
  - `route.exit ...`
  - `update.out ... handled=...`
