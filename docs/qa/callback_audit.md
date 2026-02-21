# Callback Audit (Literal `callback_data`)

## What it checks

`scripts/qa/check_callbacks.py` performs a static AST scan and compares:

1. **Used callback payloads** (from keyboard creation):
- `InlineKeyboardButton(..., callback_data="LITERAL")`
- `builder.button(..., callback_data="LITERAL")`
- Any call keyword `callback_data="LITERAL"`

2. **Handled callback payloads** (from callback decorators):
- `@router.callback_query(F.data == "LITERAL")`
- `@router.callback_query(F.data.in_(["a", "b"]))`
- `@router.callback_query(..., data="LITERAL")`
- `@router.callback_query(..., text="LITERAL")`

Then it reports:
- `missing = used - handled`
- `unused_handlers = handled - used` (warning only)

## How to run

From repository root:

```bash
python3 scripts/qa/check_callbacks.py --root bot/bot
```

JSON mode (for CI parsing):

```bash
python3 scripts/qa/check_callbacks.py --root bot/bot --json
```

On server (same):

```bash
cd /opt/vpnhub
python3 scripts/qa/check_callbacks.py --root bot/bot
```

## Exit codes

- `0` = no missing literal callback handlers found
- `2` = missing handlers found
- `1` = script/runtime error (e.g., bad path)

## How to interpret output

- **Missing callback handlers**: keyboard callback literals with no matching literal callback filter. These are likely UX dead-ends.
- **Potentially unused handled callbacks**: callback literals handled in decorators but not found as literal keyboard payloads. This is informational and can include dynamic/factory flows.

## Known limitations

- Only **literal string** callbacks are analyzed.
- Factory filters (e.g., `SomeFactory.filter()`) are intentionally ignored.
- Dynamic payload composition is not resolved.
- Regex/lambda/custom matcher semantics are not fully modeled beyond explicit literal patterns listed above.

## Sample output

```text
Root: /Users/black/Projects/vpnhub/bot/bot
Used callback_data (literals): 27
Handled callback filters (literals): 28
Missing handlers: 4
Potentially unused handlers: 5

Missing callback handlers (used but not handled):
- about_vpn_btn: bot/bot/keyboards/inline/user_inline.py:56
- affiliate_btn: bot/bot/keyboards/inline/user_inline.py:44
- help_btn: bot/bot/keyboards/inline/user_inline.py:52
- language_btn: bot/bot/keyboards/inline/user_inline.py:48
```

## How to extend later

- Add explicit support for known callback factories by parsing factory declarations and mapping encoded payload templates.
- Add optional ignore list for known dynamic callbacks.
- Add CI gate mode that fails only on new missing callbacks (baseline diff).
