# Funnel Events (Middleware-only)

## Purpose

This project logs lightweight conversion/funnel events via passive middleware, without changing handlers or business logic.

Source: `bot/bot/middlewares/conversion_events.py`

## Emitted events

One `event=conv.*` line is emitted per incoming update only when a mapped funnel signal is detected.

- `conv.start`
  - Trigger: incoming message command `/start`
- `conv.connect_click`
  - Trigger: callback payload is exactly `vpn_connect_btn`
- `conv.back_to_menu`
  - Trigger: callback payload is exactly `back_general_menu_btn`
- `conv.help_open`
  - Trigger: callback payload in:
    - `help_menu_btn`
    - `help_btn`
    - `back_help_menu`
    - `back_instructions`
- `conv.pay_open`
  - Trigger: callback payload contains substring `pay` (case-insensitive)
- `conv.pre_checkout`
  - Trigger: incoming `pre_checkout_query`
  - Extra fields: `total_amount`, `currency`
- `conv.support_message`
  - Trigger: callback payload is exactly `message_admin`

## Logged fields

Common fields:
- `event` (e.g. `conv.start`)
- `update_id`
- `update_type` (`message`, `callback_query`, `pre_checkout_query`)
- `user_id`
- `chat_id` (may be `None` for pre-checkout)
- `payload` (trimmed)

Pre-checkout only:
- `total_amount`
- `currency`

## Example log lines

```text
event=conv.start update_id=12345 update_type=message user_id=111 chat_id=111 payload='/start'
event=conv.connect_click update_id=12346 update_type=callback_query user_id=111 chat_id=111 payload='vpn_connect_btn'
event=conv.pre_checkout update_id=12347 update_type=pre_checkout_query user_id=111 chat_id=None payload='order:abc' total_amount=29900 currency=RUB
```

## Quick usage (Docker)

Stream all conversion events:

```bash
docker compose logs -f vpn_hub_bot | grep "event=conv."
```

Count events by type:

```bash
docker compose logs vpn_hub_bot | grep "event=conv\." | sed -E 's/.*event=(conv\.[^ ]+).*/\1/' | sort | uniq -c | sort -nr
```

Basic funnel snapshot (`start -> connect_click -> pay_open -> pre_checkout`):

```bash
docker compose logs vpn_hub_bot | grep -E "event=conv\.(start|connect_click|pay_open|pre_checkout)"
```

## Notes / limitations

- Middleware is passive and does not alter routing, FSM, replies, or handler results.
- Events are based on update payload patterns only.
- `conv.menu_shown` and unhandled-callback detection are intentionally not implemented at middleware level.
