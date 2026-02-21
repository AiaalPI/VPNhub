# Friction Points

## P0
1. Potential dead taps in legacy help callbacks
- Evidence: callbacks previously missing in map (`back_help_menu`, `back_instructions`, `ChooseTypeVpnHelp`) from `bot/bot/keyboards/inline/user_inline.py:515`, `602`, `612`.
- Impact: users can get stuck or lose trust in support/help path.
- Conversion impact: activation/support abandonment.

## P1
2. Catch-all fallback may hide intent during text interactions
- Evidence: `@other_router.message()` routes to main menu for unmatched messages (`bot/bot/handlers/other/main.py:23`).
- Impact: user intent can be reset instead of clarified.
- Conversion impact: increased confusion before payment/connection.

3. Payment and donate validation copy is generic
- Evidence: `error_incorrect`, `donate_input_price_text_not_num`, `donate_input_price_text_limit` (`bot/bot/handlers/user/payment_user.py:339`).
- Impact: low clarity on next required input.
- Conversion impact: payment drop-off.

4. Referral withdrawal/support FSM reuses shared state group
- Evidence: `WithdrawalFunds.input_message_admin` used by both support and withdrawal (`bot/bot/handlers/user/referral_user.py:49`, `349`, `396`).
- Impact: conceptual mismatch for users and QA complexity.
- Conversion impact: support trust and completion rate.

5. Main conversion copy is long and dense on first touch
- Evidence: `hello_message` is multi-paragraph in both locales (`bot/bot/locale/ru/LC_MESSAGES/bot.po:32`, `bot/bot/locale/en/LC_MESSAGES/bot.po:32`).
- Impact: cognitive overload before first action.
- Conversion impact: lower click-through to first key.

6. Too many callback aliases for same “home” action
- Evidence: `back_general_menu_btn`, `answer_back_general_menu_btn`, legacy `general_menu` handlers (`bot/bot/handlers/user/main.py:212`, `227`, `277`).
- Impact: analytics and UX consistency degrade.
- Conversion impact: harder to optimize “return-to-home” behavior.

## P2
7. EN copy quality inconsistencies reduce trust near purchase/support
- Evidence: awkward phrasing in locale strings (e.g., payment/support phrasing in `bot/bot/locale/en/LC_MESSAGES/bot.po`).
- Impact: perceived reliability loss for EN users.

8. Repeated media messages in callback journeys
- Evidence: mixed `answer_photo` vs `edit_message` across same flows (`bot/bot/handlers/user/main.py`, `referral_user.py`, `keys_user.py`).
- Impact: noisy chat history, weaker focus on CTA.

9. Referral block is information-heavy before primary action
- Evidence: long `affiliate_reff_text_new` text in locale files.
- Impact: lower share/withdraw CTA interaction.

10. Support CTA label does not set expected response SLA
- Evidence: `help_btn` leads to generic “leave a message” copy (`input_message_user_admin`).
- Impact: user may defer asking for help instead of completing purchase/connect.
