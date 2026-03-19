# Friction Points

## P0
1. No confirmed literal dead taps in current callback map
- Evidence: `scripts/qa/check_callbacks.py --root bot/bot` now reports `Missing handlers: 0`.
- Impact: previous P0 callback gaps are closed; this item remains only as regression-watch guidance.

## P1
2. Catch-all fallback may hide intent during text interactions
- Evidence: outside active FSM, unmatched messages still return to main menu.
- Impact: lower than before, because active FSM is now explicitly guarded.
- Conversion impact: residual confusion risk outside structured flows.

3. Payment and donate validation copy is generic
- Evidence: `error_incorrect`, `donate_input_price_text_not_num`, `donate_input_price_text_limit` (`bot/bot/handlers/user/payment_user.py:339`).
- Impact: low clarity on next required input.
- Conversion impact: payment drop-off.

4. Hidden promo branch remains parked for future reuse
- Evidence: `promokod_btn` handler still exists, but it is intentionally hidden from the current primary user menu and mailing paths.
- Impact: code/docs/product intent diverge.
- Conversion impact: experimentation and analytics around these branches are harder to trust.

5. Main conversion copy is long and dense on first touch
- Evidence: `hello_message` is multi-paragraph in both locales (`bot/bot/locale/ru/LC_MESSAGES/bot.po:32`, `bot/bot/locale/en/LC_MESSAGES/bot.po:32`).
- Impact: cognitive overload before first action.
- Conversion impact: lower click-through to first key.

6. Legacy callback alias still exists for old messages
- Evidence: new keyboards now use `back_general_menu_btn`, while `answer_back_general_menu_btn` remains only as a backward-compatible handler alias.
- Impact: small residual analytics noise from old messages.
- Conversion impact: low; the main contract is now simpler for new flows.

## P2
7. EN copy quality inconsistencies reduce trust near purchase/support
- Evidence: awkward phrasing in locale strings (e.g., payment/support phrasing in `bot/bot/locale/en/LC_MESSAGES/bot.po`).
- Impact: perceived reliability loss for EN users.

8. Repeated media messages in callback journeys
- Evidence: mixed `answer_photo` vs `edit_message` across same flows (`bot/bot/handlers/user/main.py`, `referral_user.py`, `keys_user.py`).
- Impact: noisy chat history, weaker focus on CTA.

9. Referral block is information-heavy before primary action
- Evidence: long `referral_program_text` text in locale files.
- Impact: lower share/withdraw CTA interaction.

10. Support CTA label does not set expected response SLA
- Evidence: `help_btn` leads to generic “leave a message” copy (`input_message_user_admin`).
- Impact: user may defer asking for help instead of completing purchase/connect.
