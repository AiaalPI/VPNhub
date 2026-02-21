# AS-IS UX Map (Current Implementation)

## Scope and Sources
- Scope: only implemented user UX in current codebase.
- Entry/runtime: `bot/bot/main.py`, `bot/bot/handlers/user/*.py`, `bot/bot/keyboards/inline/user_inline.py`, `bot/bot/misc/callbackData.py`, locales `bot/bot/locale/{ru,en}/LC_MESSAGES/bot.po`.
- This map excludes admin panel internals.

## Runtime Entry Points and Routing
- Bot command entry: `/start` via `registered_router.message(Command("start"))` in `bot/bot/handlers/user/main.py:93`.
- Main dispatcher includes routers in order: `registered_router -> user_router -> get_key_router -> admin_router -> other_router` in `bot/bot/main.py:103`.
- Private messages only: `dp.message.filter(PrivateFilter())` in `bot/bot/main.py:110`.
- Allowed updates are dynamic from handlers: `dp.resolve_used_update_types()` logged as `startup.polling_ready` in `bot/bot/main.py:170`.
- Global fallback for unmatched messages: `other_router.message()` returns main menu photo in `bot/bot/handlers/other/main.py:23`.

## Commands and Menu Entry
- Bot commands registered: only `/start` in `bot/bot/misc/commands.py:5`.
- Main menu keyboard (`user_menu`):
  - `🌍 Подключить VPN / 🌍 Connect VPN` -> `vpn_connect_btn`
  - `👥️ Партнёр / 👥 Affiliate` -> `affiliate_btn`
  - `🌍 Language` -> `language_btn`
  - `📥 Поддержка / 📥 Support` -> `help_btn`
  - `🗞 О нас / 🗞 About VPN` -> `about_vpn_btn`
  - (+ admin button if admin user)
  - Source: `bot/bot/keyboards/inline/user_inline.py:35`.

## Logging of Handling
- Incoming/outgoing updates logged with handled flag:
  - `update.in ... payload=...`
  - `update.out ... handled=<bool>`
  - Source: `bot/bot/middlewares/update_logging.py:40`.
- Route-level handler logging:
  - `route.enter ... handler=<module.fn>`
  - `route.exit ... status=ok`
  - Source: `bot/bot/middlewares/update_logging.py:75`.

## FSM States and Transitions
- `ActivatePromocode.input_promo`
  - enter: callback `promo_code` -> ask promo text (`referral_user.py:158`)
  - exit: after validation, always `state.clear()` (`referral_user.py:336`).
- `WithdrawalFunds`:
  - `input_amount` -> `payment_method` -> `communication` (`referral_user.py:172`, `188`, `213`, `225`)
  - support message also reuses `input_message_admin` (`referral_user.py:339`, `354`, `370`, `386`).
- `Price.input_price` for donation custom amount (`payment_user.py:311`, `339`).

## AS-IS Screen/State Catalog

### S01. Start: New user welcome
- Trigger: `/start` for new person (`created_now=True`) in `main.py:144`.
- Message RU: long `hello_message` promo text.
- Message EN: long `hello_message` promo text.
- Media: `bot/img/hello_bot.jpg`.
- Next: immediate trial issuance via `issue_trial_from_start(...)` (`main.py:170`).
- Recovery: no explicit buttons on this message.

### S02. Start: Existing user main menu
- Trigger: `/start` existing user or after follow-check success (`main.py:181`, `85`).
- Message: photo-only `bot/img/main_menu.jpg`.
- Buttons: main menu (`user_menu`) with callback set above.
- Back/Home: n/a (this is home).

### S03. Subscription gate
- Trigger: blocked by follow check (`filters/main.py:48`).
- Message RU/EN: `no_follow` + channel URL + check button.
- Buttons:
  - `{CONFIG.name_channel}` (URL)
  - `Проверить подписку` (`no_follow_button`) -> `check_follow_chanel`
- Next: callback handler checks membership and returns to S02 (`main.py:76`).

### S04. Connect VPN root (has keys)
- Trigger: `vpn_connect_btn` when keys exist (`keys_user.py:52`).
- Message RU/EN: `user_key_list_message_connect`.
- Media: `bot/img/keys_user.jpg`.
- Buttons from `connect_vpn_menu`:
  - `Создать новый ключ` -> `generate_new_key`
  - each key row -> `DetailKey(key_id)`
  - `Главное меню` -> `back_general_menu_btn`
- Next: key detail / key generation.

### S05. Connect VPN root (no keys)
- Trigger: `vpn_connect_btn` when no keys (`keys_user.py:70`).
- Message RU/EN: `choosing_connect_type`.
- Buttons: dynamic protocols -> `ChooseTypeVpn(type_vpn,key_id,payment=True)`.
- Back/Home: button label from `admin_back_admin_menu_btn`, callback `back_general_menu_btn` (`user_inline.py:297`).

### S06. Location selection
- Trigger: after protocol selection when >1 location (`main.py:455`, `edit_or_get_key.py:303`).
- Message RU/EN: `choosing_connect_location`.
- Buttons:
  - each location name -> `ChooseLocation(id_location,key_id,type_vpn,payment=...)`
  - back -> `back_general_menu_btn` (payment flow) or `BackTypeVpn` (edit flow)
- Next:
  - payment flow -> tariff screen (`payment_choosing_vpn`)
  - edit/switch flow -> key reprovision + connection message.

### S07. Tariff selection (buy/renew)
- Trigger:
  - new purchase path from `ChooseLocation(payment=True)` (`edit_or_get_key.py:142`)
  - renew path from `ExtendKey` (`keys_user.py:364`).
- Message RU/EN: `choosing_month_sub`.
- Buttons:
  - 1/3/6/12 month -> `ChoosingMonths(...)`
  - optional trial -> `TrialPeriod(id_prot,id_loc)`
  - back -> callback in `back_data` (`vpn_connect_btn` or `back_general_menu_btn`)

### S08. Promo decision and payment method
- Trigger: `ChoosingMonths` (`payment_user.py:92`).
- Message RU/EN:
  - `want_use_promocode` if available promo
  - or `method_replenishment`.
- Buttons:
  - promo options -> `PromoCodeChoosing(...)`
  - payment providers -> `ChoosingPrise(...)`
  - fallback no providers -> `none` / `none`
  - back -> `answer_back_general_menu_btn`

### S09. Payment initiation
- Trigger: `ChoosingPrise` (`payment_user.py:203`).
- Message: delegated to selected payment class (`to_pay()`).
- Typical keyboard from helpers: pay URL/webapp/pay stars + `answer_back_general_menu_btn`.
- Recovery: main menu via callback `answer_back_general_menu_btn`.

### S10. Trial issuance
- Trigger:
  - auto on new `/start` (`main.py:170`)
  - manual `ConnectMenu(action='prob_period')` (`main.py:345`)
  - tariff screen trial button `TrialPeriod` (`keys_user.py:114`).
- Message RU/EN:
  - `trial_message` (explicitly 3 days in both locales)
  - then `download`
  - then connection instruction message.
- Back/Home: in final instruction keyboard `answer_back_general_menu_btn`.

### S11. Key detail actions
- Trigger: `DetailKey(key_id)` (`keys_user.py:279`).
- Message: same key list message with expanded controls.
- Buttons for selected key:
  - `Получить` -> `ShowKey(key_id)`
  - `Продлить` -> `ExtendKey(key_id)`
  - `Изменить` -> `EditKey(key_id)` (if enabled)
  - global back -> `back_general_menu_btn`

### S12. Key delivery / instructions
- Trigger: `ShowKey` or successful issue/provision (`keys_user.py:311`, `edit_or_get_key.py:161`).
- Message RU/EN:
  - `how_to_connect` / `how_to_connect_wg` / `how_to_connect_remnawave`.
- Buttons from `instruction_manual`:
  - iOS/Android/PC instruction URLs (by protocol)
  - `Проверить VPN / Check VPN` URL
  - `Главное меню` -> `answer_back_general_menu_btn`
  - for Remnawave type 6: `ShowUserDevices(key_id)` option.

### S13. Referral main
- Trigger: `affiliate_btn` (`referral_user.py:93`).
- Message RU/EN: long `affiliate_reff_text_new` with link/stats/balance.
- Buttons:
  - `Поделиться` URL
  - conditional withdraw button -> `withdrawal_of_funds` or disabled `none`
  - `Главное меню` -> `back_general_menu_btn`

### S14. Withdraw referral funds (FSM)
- Trigger: `withdrawal_of_funds` (`referral_user.py:172`).
- Steps/messages:
  - ask amount: `input_amount_withdrawal_min`
  - ask transfer details: `where_transfer_funds`
  - ask contact: `how_i_contact_you`
  - success/error: `referral_system_success` or `error_withdrawal_funds_not_balance`
- Back/Home: no explicit inline buttons during text-step states.

### S15. Promo code flow (FSM)
- Trigger: `promokod_btn` screen -> `promo_code` callback (`referral_user.py:64`, `158`).
- Message RU/EN: `referral_promo_code`, then `input_promo_user`.
- Buttons on promo screen:
  - `Ввести...` -> `promo_code`
  - `Главное меню` -> `back_general_menu_btn`
- Outcomes:
  - discount promo: `promo_success_percent_user`
  - bonus-day promo: `promo_success_day_user` + key-selection keyboard.

### S16. Support flow
- Trigger: `help_btn` or `message_admin` callback (`referral_user.py:339`, `354`).
- Message RU/EN: `input_message_user_admin`.
- Buttons:
  - from help screen: `back_general_menu_btn`
- FSM: waits `WithdrawalFunds.input_message_admin` then forwards to admin and confirms (`message_user_admin_success`).

### S17. Language selection
- Trigger: `language_btn` (`main.py:469`, `479`).
- Message RU/EN: `select_language`.
- Buttons: `ChoosingLang(lang='ru'|'en')`.
- Next: updates user lang, shows main menu photo (`main.py:500`).

### S18. About screen
- Trigger: `about_vpn_btn` (`main.py:522`, `537`).
- Message RU/EN: `about_message`.
- Media: `bot/img/about.jpg`.
- Buttons: `back_general_menu_btn`.

### S19. Donate flow
- Trigger: `donate_btn` (`payment_user.py:265`).
- Message RU/EN: `donate_message`.
- Buttons:
  - predefined amounts -> `DonatePrice(price)`
  - custom amount -> `DonatePrice(price=0)` -> FSM `Price.input_price`
  - donors list -> `donate_list`
  - main menu -> `back_general_menu_btn`
- Donation list screen has back only to donate menu: `back_donate_menu`.

### S20. Free VPN (feature-flagged filter)
- Trigger: `free_vpn_connect_btn` (`free_vpn.py:39`).
- Message flow: `download` -> issue/reuse free key -> instruction screen.
- If unavailable: `not_server_free_vpn` + `back_general_menu_btn`.

## Key Callback Data Values (User UX)
- Main nav: `vpn_connect_btn`, `affiliate_btn`, `language_btn`, `help_btn`, `about_vpn_btn`, `back_general_menu_btn`, `answer_back_general_menu_btn`.
- Connection: `generate_new_key`, `ConnectMenu(action=...)`, `ChooseTypeVpn(...)`, `ChooseLocation(...)`, `BackTypeVpn(...)`, `DetailKey(...)`, `ShowKey(...)`, `EditKey(...)`, `ExtendKey(...)`, `TrialPeriod(...)`.
- Referral/support: `promokod_btn`, `promo_code`, `withdrawal_of_funds`, `ReferralKeys(...)`, `message_admin`.
- Payments/donate: `ChoosingMonths(...)`, `PromoCodeChoosing(...)`, `ChoosingPrise(...)`, `DonatePrice(...)`, `donate_list`, `back_donate_menu`, plus `none` placeholder callbacks.
- Remnawave devices: `ShowUserDevices(...)`, `RemoveUserDevices(...)`.
