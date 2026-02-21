# Unhandled Callbacks

Detected from inline keyboards (`bot/bot/keyboards/inline/*`) against callback handlers (`bot/bot/handlers/*`).

## Definitely Unhandled (P0/P1)

| callback_data | source (button) | evidence | severity | impact |
|---|---|---|---|---|
| `none protocol` | `bot/bot/keyboards/inline/user_inline.py:294` | No `F.data == 'none protocol'` or equivalent handler in user/admin handlers | P1 | User can tap non-working button if no VPN types are available |
| `back_instructions` | `bot/bot/keyboards/inline/user_inline.py:519` | No handler for `back_instructions` in repo | P1 | “Back” from instruction helper is broken if keyboard is used |
| `back_help_menu` | `bot/bot/keyboards/inline/user_inline.py:606` and `bot/bot/keyboards/inline/user_inline.py:621` | No handler for `back_help_menu` in repo | P1 | Help submenu back action is broken if keyboard is used |
| `ChooseTypeVpnHelp(*)` | `bot/bot/keyboards/inline/user_inline.py:615`, `bot/bot/keyboards/inline/user_inline.py:617` | No `@*.callback_query(ChooseTypeVpnHelp.filter())` handler in repo | P1 | Help VPN type buttons have no route |

## Notes

- `none` callbacks are covered by explicit alert handler: `bot/bot/handlers/user/main.py:241`.
- Dynamic callback in `mailing_button_message` (`callback_data=_(text, lang)`) is runtime-dependent and can map to unhandled values; requires controlled config review.
