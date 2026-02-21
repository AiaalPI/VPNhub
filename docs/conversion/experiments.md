# Conversion Experiments (Low-Risk, High-Impact)

## Experiment 1: Short welcome copy vs current long copy
- Hypothesis: shorter `/start` copy increases click to first key action.
- A: current `hello_message`.
- B: 3-line concise value proposition + explicit trial CTA.
- Metric: `% users reaching key delivery screen within 2 minutes of /start`.
- Guardrail: support messages per new user should not increase >10%.

## Experiment 2: Trial CTA prominence
- Hypothesis: explicit “3 days free” CTA increases first-session activation.
- A: current trial CTA placement.
- B: trial CTA as first button for eligible users.
- Metric: `% eligible users who activate trial`.
- Guardrail: paid conversion D7 should not decline.

## Experiment 3: Payment step clarity
- Hypothesis: clearer payment step copy reduces payment abandonment.
- A: current `method_replenishment` text.
- B: explicit “choose method, then complete payment in opened page”.
- Metric: `% users reaching provider invoice after month selection`.
- Guardrail: error callback volume unchanged.

## Experiment 4: FSM error helper copy
- Hypothesis: example-based validation copy increases form completion.
- A: generic invalid input message.
- B: invalid input + example format.
- Metric: `% users completing donate/withdraw FSM after first error`.
- Guardrail: average step time not worse than +15%.

## Experiment 5: Support reassurance microcopy
- Hypothesis: response-expectation copy increases trust and prevents churn.
- A: current support prompt.
- B: prompt with clear response expectation in same chat.
- Metric: `% users who return to connect/payment flow within 24h after support prompt`.
- Guardrail: admin message load remains manageable.

## Experiment 6: Unified Back/Main menu visibility
- Hypothesis: persistent recovery CTA reduces dead-end exits.
- A: current mixed recovery visibility.
- B: explicit `back_general_menu_btn` at all FSM prompts.
- Metric: `% sessions with no further action after validation error` (lower is better).
- Guardrail: no increase in unintended flow resets.

## Rollout order
1. Exp 1 (welcome copy)
2. Exp 3 (payment clarity)
3. Exp 4 (input validation copy)
4. Exp 6 (recovery CTA visibility)
5. Exp 2 (trial prominence)
6. Exp 5 (support reassurance)
