# Callback Index (AS-IS)

Source baseline: current handlers in `bot/bot/handlers/*` and inline keyboards in `bot/bot/keyboards/inline/*`.

## Main Menu / Entry

| callback_data | handler function | file:line | router | notes |
|---|---|---|---|---|
| `check_follow_chanel` | `connect_vpn` | `bot/bot/handlers/user/main.py:76` | `registered_router` | Post-subscription check from `/start` gating keyboard |
| `vpn_connect_btn` | `choose_server_user` | `bot/bot/handlers/user/keys_user.py:52` | `key_router` | Main connect flow |
| `vpn_connect_btn` (localized variant) | `choose_server_user` | `bot/bot/handlers/user/keys_user.py:83` | `key_router` | Duplicate route style (`btn_text`) |
| `affiliate_btn` | `referral_system_handler` | `bot/bot/handlers/user/referral_user.py:93` | `referral_router` | Referral hub |
| `affiliate_btn` (localized variant) | `referral_system_handler` | `bot/bot/handlers/user/referral_user.py:124` | `referral_router` | Duplicate route style (`btn_text`) |
| `language_btn` | `choose_server_user` | `bot/bot/handlers/user/main.py:495` | `user_router` | Language chooser |
| `language_btn` (localized variant) | `choose_server_user` | `bot/bot/handlers/user/main.py:485` | `user_router` | Duplicate route style (`btn_text`) |
| `help_btn` | `info_message_handler` | `bot/bot/handlers/user/referral_user.py:364` | `referral_router` | Support flow |
| `help_btn` (localized variant) | `info_message_handler` | `bot/bot/handlers/user/referral_user.py:380` | `referral_router` | Duplicate route style (`btn_text`) |
| `about_vpn_btn` | `info_message_handler` | `bot/bot/handlers/user/main.py:553` | `user_router` | About screen |
| `about_vpn_btn` (localized variant) | `info_message_handler` | `bot/bot/handlers/user/main.py:538` | `user_router` | Duplicate route style (`btn_text`) |
| `admin_panel_btn` | `admin_menu_callback` | `bot/bot/handlers/admin/main.py:84` | `admin_router` | Admin entry |
| `none` | `unavailable_action` | `bot/bot/handlers/user/main.py:241` | `user_router` | Explicit alert handler |
| `back_general_menu_btn` | `back_main_menu` | `bot/bot/handlers/user/main.py:212` | `user_router` | Recovery to main menu |
| `answer_back_general_menu_btn` | `back_main_menu` | `bot/bot/handlers/user/main.py:227` | `user_router` | Recovery to main menu |
| `general_menu` | `get_general_menu` | `bot/bot/handlers/user/main.py:277` | `user_router` | Legacy callback (not found in current keyboards) |

## VPN / Connect / Keys

| callback_data | handler function | file:line | router | notes |
|---|---|---|---|---|
| `ConnectMenu(*)` | `connect_menu_handler` | `bot/bot/handlers/user/main.py:336` | `user_router` | `connect_vpn` / `prob_period` actions |
| `ChooseTypeVpn(*)` | `choose_server_free` | `bot/bot/handlers/user/main.py:436` | `user_router` | VPN type selection |
| `BackTypeVpn(*)` | `call_choose_server` | `bot/bot/handlers/user/main.py:403` | `user_router` | Back from location/type |
| `ChooseLocation(*)` | `select_location_callback` | `bot/bot/handlers/user/edit_or_get_key.py:51` | `get_key_router` | Location select + key binding |
| `TrialPeriod(*)` | `choose_server_user` | `bot/bot/handlers/user/keys_user.py:114` | `key_router` | Trial key issue |
| `DetailKey(*)` | `callback_price` | `bot/bot/handlers/user/keys_user.py:279` | `key_router` | Key card details |
| `ShowKey(*)` | `callback_price` | `bot/bot/handlers/user/keys_user.py:311` | `key_router` | Show config |
| `EditKey(*)` | `callback_price` | `bot/bot/handlers/user/keys_user.py:340` | `key_router` | Change location |
| `ExtendKey(*)` | `callback_price` | `bot/bot/handlers/user/keys_user.py:364` | `key_router` | Renew key |
| `ShowUserDevices(*)` | `show_user_devices_callback` | `bot/bot/handlers/user/edit_or_get_key.py:340` | `get_key_router` | Remnawave devices |
| `RemoveUserDevices(*)` | `remove_user_devices_callback` | `bot/bot/handlers/user/edit_or_get_key.py:377` | `get_key_router` | Remove device |
| `generate_new_key` | `generate_new_key` | `bot/bot/handlers/user/main.py:315` | `user_router` | Create additional key |

## Subscription / Buy / Renew / Donate

| callback_data | handler function | file:line | router | notes |
|---|---|---|---|---|
| `ChoosingMonths(*)` | `my_callback_foo` | `bot/bot/handlers/user/payment_user.py:92` | `callback_user` | Month plan selection |
| `PromoCodeChoosing(*)` | `callback_price` | `bot/bot/handlers/user/payment_user.py:152` | `callback_user` | Promo at checkout |
| `ChoosingPyment(*)` | `callback_price` | `bot/bot/handlers/user/payment_user.py:188` | `callback_user` | Payment method group |
| `ChoosingPrise(*)` | `callback_payment` | `bot/bot/handlers/user/payment_user.py:203` | `callback_user` | Final payment action |
| `AutoPay(*)` | `callback_price` | `bot/bot/handlers/user/payment_user.py:75` | `callback_user` | Auto-pay toggle |
| `donate_btn` | `renew_subscription` | `bot/bot/handlers/user/payment_user.py:265` | `callback_user` | Donate screen |
| `donate_btn` (localized variant) | `renew_subscription` | `bot/bot/handlers/user/payment_user.py:281` | `callback_user` | Duplicate route style (`btn_text`) |
| `DonatePrice(*)` | `callback_payment` | `bot/bot/handlers/user/payment_user.py:311` | `callback_user` | Donate amount |
| `donate_list` | `callback_payment` | `bot/bot/handlers/user/payment_user.py:369` | `callback_user` | Donors list |
| `back_donate_menu` | `callback_payment` | `bot/bot/handlers/user/payment_user.py:296` | `callback_user` | Back to donate menu |

## Referral / Support

| callback_data | handler function | file:line | router | notes |
|---|---|---|---|---|
| `promokod_btn` | `give_handler` | `bot/bot/handlers/user/referral_user.py:64` | `referral_router` | Promo screen |
| `promokod_btn` (localized variant) | `give_handler` | `bot/bot/handlers/user/referral_user.py:79` | `referral_router` | Duplicate route style (`btn_text`) |
| `promo_code` | `successful_payment` | `bot/bot/handlers/user/referral_user.py:158` | `referral_router` | Prompt promo text input |
| `withdrawal_of_funds` | `withdrawal_of_funds` | `bot/bot/handlers/user/referral_user.py:172` | `referral_router` | Withdrawal FSM entry |
| `message_admin` | `message_admin` | `bot/bot/handlers/user/referral_user.py:349` | `referral_router` | Direct contact callback |
| `ReferralKeys(*)` | `message_admin` | `bot/bot/handlers/user/referral_user.py:429` | `referral_router` | Referral bonus to key |

## Language

| callback_data | handler function | file:line | router | notes |
|---|---|---|---|---|
| `ChoosingLang(*)` | `deposit_balance` | `bot/bot/handlers/user/main.py:516` | `user_router` | Save selected language |

## Admin (present)

| callback_data | handler function | file:line | router | notes |
|---|---|---|---|---|
| `add_location` | `add_location_callback` | `bot/bot/handlers/admin/location_control.py:156` | `location_control` | Location create flow |
| `back_location_list` | `back_location_list` | `bot/bot/handlers/admin/location_control.py:81` | `location_control` | Back to locations list |
| `locations_statistic` | `show_locations_statistic` | `bot/bot/handlers/admin/location_control.py:626` | `location_control` | Stats screen |
| `new_promo` | `new_promo` | `bot/bot/handlers/admin/referal_admin.py:120` | `referral_router` | Promo create |
| `show_promo` | `show_promo` | `bot/bot/handlers/admin/referal_admin.py:276` | `referral_router` | Promo list |
| `show_all_metrics` | `show_all_metrics` | `bot/bot/handlers/admin/metric_management.py:67` | `metric_management_router` | Metrics list |
| `add_metric` | `add_metric` | `bot/bot/handlers/admin/metric_management.py:132` | `metric_management_router` | Metrics create |
| `statistic_metric` | `show_metric_statistic` | `bot/bot/handlers/admin/metric_management.py:168` | `metric_management_router` | Metrics stats |
| `skip_input_caddy_token` | `skip_input_caddy_token` | `bot/bot/handlers/admin/protocol_control.py:282` | `state_admin_router` | Optional Caddy token |
| `none` | `unavailable_action` | `bot/bot/handlers/user/main.py:241` | `user_router` | Used by admin metric keyboard placeholder |
