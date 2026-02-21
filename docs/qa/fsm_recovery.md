# FSM Recovery Audit (AS-IS)

Scope: user-facing FSM in `bot/bot/handlers/user/*`.

## FSM Groups and States

### `ActivatePromocode`

| state | entry point | expected input | recovery UI present | handler |
|---|---|---|---|---|
| `input_promo` | callback `promo_code` asks `input_promo_user` | promo text | No explicit back button in entry prompt | `bot/bot/handlers/user/referral_user.py:158`, `bot/bot/handlers/user/referral_user.py:279` |

Assessment: **P1** (recoverable via generic main-menu callbacks/messages, but no explicit recovery on prompt).

### `WithdrawalFunds`

| state | entry message | expected input | recovery buttons | handler evidence |
|---|---|---|---|---|
| `input_amount` | `input_amount_withdrawal_min` | integer amount | `back_general_menu_btn` via `back_menu_button` | `bot/bot/handlers/user/referral_user.py:172` |
| `payment_method` | `where_transfer_funds` | payment details text | `back_general_menu_btn` via `back_menu_button` | `bot/bot/handlers/user/referral_user.py:215` |
| `communication` | `how_i_contact_you` | contact text | `back_general_menu_btn` via `back_menu_button` | `bot/bot/handlers/user/referral_user.py:230` |
| `input_message_admin` | `input_message_user_admin` (help/support flows) | free text to admin | back button attached in help screen; direct `message_admin` callback has no back markup | `bot/bot/handlers/user/referral_user.py:349`, `bot/bot/handlers/user/referral_user.py:364`, `bot/bot/handlers/user/referral_user.py:380` |

Assessment:
- `input_amount/payment_method/communication`: **OK** (explicit recovery shown).
- `input_message_admin`: **P1** for branch entered via callback `message_admin` (`bot/bot/handlers/user/referral_user.py:349`) because prompt has no reply_markup.

### `Price`

| state | entry message | expected input | recovery buttons | handler evidence |
|---|---|---|---|---|
| `input_price` | `donate_input_price_text` | numeric amount 50..20000 | has back button on entry; validation errors return text-only message | `bot/bot/handlers/user/payment_user.py:311`, `bot/bot/handlers/user/payment_user.py:339` |

Assessment: **P1** (initial recovery exists, but invalid input responses do not re-attach recovery keyboard).

## Trap Risk Summary

- **P0:** none confirmed for active user flows.
- **P1:** missing explicit recovery in some FSM prompts/validation branches (`input_promo`, `message_admin`, `Price.input_price` invalid branch).
