# Funnel Map (AS-IS)

## Funnel A: Activation (New User -> Trial Key)
1. `/start` -> `registered_router.message(Command("start"))` (`bot/bot/handlers/user/main.py:93`)
2. New user branch -> welcome photo/text + auto trial issue (`bot/bot/handlers/user/main.py:144`)
3. Trial issuance -> `issue_trial_from_start(...)` (`bot/bot/handlers/user/main.py:170` -> `bot/bot/handlers/user/keys_user.py:207`)
4. Key provisioning -> `get_trial_period(...)` (`bot/bot/handlers/user/keys_user.py:129`)
5. Connection instructions delivered -> `post_key_telegram(...)` (`bot/bot/handlers/user/edit_or_get_key.py:161`)

Primary conversion event: user receives valid connection key + instruction buttons.

## Funnel B: Existing User -> Connect
1. `/start` -> main menu photo (`bot/bot/handlers/user/main.py:257`)
2. Tap `vpn_connect_btn` -> key list or protocol/location selector (`bot/bot/handlers/user/keys_user.py:52`)
3. If key exists: `DetailKey/ShowKey` path (`bot/bot/handlers/user/keys_user.py:279`, `311`)
4. If no key: choose protocol/location (`bot/bot/handlers/user/main.py:436`, `bot/bot/handlers/user/edit_or_get_key.py:51`)
5. Receive instruction screen (`bot/bot/handlers/user/edit_or_get_key.py:161`)

Primary conversion event: key opened in client app.

## Funnel C: Purchase / Renewal
1. From key flow -> tariff (`renew`) and month selection (`ChoosingMonths`) (`bot/bot/handlers/user/payment_user.py:92`)
2. Optional promo selection (`PromoCodeChoosing`) (`bot/bot/handlers/user/payment_user.py:152`)
3. Payment provider selection (`ChoosingPrise`) (`bot/bot/handlers/user/payment_user.py:203`)
4. Invoice/payment start in provider class (`to_pay()` call in `pay_payment`) (`bot/bot/handlers/user/payment_user.py:241`)

Primary conversion event: successful payment callback handling and active subscription.

## Funnel D: Referral-assisted Monetization
1. Main menu -> `affiliate_btn` (`bot/bot/handlers/user/referral_user.py:93`)
2. Referral screen with share URL and balance (`share_link`) (`bot/bot/keyboards/inline/user_inline.py:529`)
3. Withdraw flow entry (`withdrawal_of_funds`) (`bot/bot/handlers/user/referral_user.py:172`)

Primary conversion event: referral share click / completed withdrawal request.

## Drop-off hotspots (AS-IS)
- Subscription gate (`check_follow_chanel`) before activation.
- Multi-step protocol+location+tariff path for users without key.
- Payment provider mismatch/unavailable state.
- Support and recovery steps that can feel non-linear.
