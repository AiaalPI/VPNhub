# Duplicates and Unreachable UX Routes

## Duplicate Callback Handlers

Potential duplicates (same semantic action handled by multiple filters):

| callback/action | handlers | evidence | risk |
|---|---|---|---|
| `vpn_connect_btn` | literal + localized filter | `bot/bot/handlers/user/keys_user.py:52`, `bot/bot/handlers/user/keys_user.py:83` | P2: maintenance duplication, order sensitivity |
| `affiliate_btn` | literal + localized filter | `bot/bot/handlers/user/referral_user.py:93`, `bot/bot/handlers/user/referral_user.py:124` | P2 |
| `help_btn` | literal + localized filter | `bot/bot/handlers/user/referral_user.py:364`, `bot/bot/handlers/user/referral_user.py:380` | P2 |
| `language_btn` | literal + localized filter | `bot/bot/handlers/user/main.py:485`, `bot/bot/handlers/user/main.py:495` | P2 |
| `about_vpn_btn` | literal + localized filter | `bot/bot/handlers/user/main.py:538`, `bot/bot/handlers/user/main.py:553` | P2 |
| `donate_btn` | literal + localized filter | `bot/bot/handlers/user/payment_user.py:265`, `bot/bot/handlers/user/payment_user.py:281` | P2 |
| `promokod_btn` | literal + localized filter | `bot/bot/handlers/user/referral_user.py:64`, `bot/bot/handlers/user/referral_user.py:79` | P2 |

## Unreachable / Dead UX Functions

| function/screen | evidence | assessment |
|---|---|---|
| `show_start_message_new_user` | Defined at `bot/bot/handlers/user/main.py:262`, no references found in repo | Unreachable UX branch (dead code) |
| `connect_menu` keyboard builder | Defined at `bot/bot/keyboards/inline/user_inline.py:257`, no references found in repo | Unused UI constructor |
| `choose_type_vpn_help` keyboard builder | Defined at `bot/bot/keyboards/inline/user_inline.py:612`, no references found in repo | Unused helper; also has unhandled callbacks |
| `back_help_menu` keyboard builder | Defined at `bot/bot/keyboards/inline/user_inline.py:602`, no references found in repo | Unused helper; no callback handler |
| `back_instructions` keyboard builder | Defined at `bot/bot/keyboards/inline/user_inline.py:515`, no references found in repo | Unused helper; no callback handler |
| `trial_pay_button` keyboard builder | Defined at `bot/bot/keyboards/inline/user_inline.py:764`, no references found in repo | Unused UI path |

## Fallback Router Behavior (Catch-all)

- Catch-all message handler: `bot/bot/handlers/other/main.py:23` (`@other_router.message()`)
- Behavior: any unmatched user private message returns main menu image/keyboard.
- Risk: can hide broken command/text flows (user sees menu instead of explicit error).
- QA test focus:
  - send unknown text in active FSM state;
  - send unknown text outside FSM;
  - verify no critical state is silently reset without user explanation.
