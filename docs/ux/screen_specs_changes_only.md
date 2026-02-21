# Screen Specs (Changes Only)

## 1) Key Detail Actions (EN)
- Current location: `bot/bot/keyboards/inline/user_inline.py:710` + `bot/bot/locale/en/LC_MESSAGES/bot.po`.

Before
- Message: `Your keys` list with expanded actions.
- Buttons: `[empty]`, `[empty]`, `[empty]` for get/renew/edit in EN.

After
- Message: unchanged.
- Buttons:
  - `Get key` -> `ShowKey(key_id)`
  - `Renew` -> `ExtendKey(key_id)`
  - `Change location` -> `EditKey(key_id)`

## 2) Disabled Action Feedback (`none` callback)
- Current location: `bot/bot/keyboards/inline/user_inline.py:204`, `205`, `544`.

Before
- Message: unchanged screen.
- Buttons: tap on disabled option does nothing.

After
- Message: unchanged.
- Behavior on tap `none`: show alert text:
  - RU: `Сейчас это действие недоступно.`
  - EN: `This action is currently unavailable.`

## 3) Protocol/Tariff Back Label
- Current location: `bot/bot/keyboards/inline/user_inline.py:299`, `372`.

Before
- Back button label uses admin key (`admin_back_admin_menu_btn`).
- Callback: `back_general_menu_btn` or passed `back_data`.

After
- Label: `back_general_menu_btn` (user-facing).
- Callback: unchanged.

## 4) Withdrawal FSM Prompts (Recovery)
- Current location: `bot/bot/handlers/user/referral_user.py:180`, `209`, `221`.

Before
- Text prompts only, no inline navigation.
- User can get stuck typing invalid/free text loop.

After
- Same prompt text, plus inline keyboard:
  - `Главное меню / Main menu` -> `back_general_menu_btn`

## 5) Help/Support State Isolation
- Current location: `bot/bot/handlers/user/referral_user.py:49`, `350`, `367`, `386`.

Before
- Support input uses `WithdrawalFunds.input_message_admin`.

After
- New state group for support (e.g., `SupportState.input_message_admin`).
- Support messages/handlers bound only to support state.

## 6) Callback Navigation Consistency (high-traffic screens)
- Current locations: `main.py:191`, `235`, `529`; `keys_user.py:94`; `referral_user.py:151`.

Before
- Mixed behavior: some callbacks edit message, others send new photo messages.

After
- Callback-driven screens use edit/update where possible.
- Message stack growth reduced; latest state remains in one screen thread.
