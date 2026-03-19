# FSM Recovery Audit (AS-IS)

Last reviewed against current code: 2026-03-18.

Scope: user-facing FSM in `bot/bot/handlers/user/*`.

## FSM Groups and States

### `ActivatePromocode`

| state | entry point | expected input | recovery UI present | handler |
|---|---|---|---|---|
| `input_promo` | callback `promo_code` asks `input_promo_user` | promo text | back button present via `back_menu_button` | `bot/bot/handlers/user/referral_user.py` |

Assessment: **OK**.

### `Price`

| state | entry message | expected input | recovery buttons | handler evidence |
|---|---|---|---|---|
| `input_price` | `donate_input_price_text` | numeric amount 50..20000 | back button present on entry and validation branches | `bot/bot/handlers/user/payment_user.py` |

Assessment: **OK**.

## Trap Risk Summary

- **P0:** none confirmed for active user flows.
- **P1:** none confirmed in currently verified FSM recovery paths.
