# Conversion Agent Brief — VPNHub Telegram Bot

## Goal
Increase product conversion in the current Telegram bot UX without changing business logic.
Primary KPI: reduce time from `/start` to successful VPN connection/payment action.

## Scope
Analyze only implemented UX in repository code:
- handlers and callback routing
- inline/reply keyboards
- user-visible copy (RU/EN)
- FSM prompts and recovery

Do not redesign from scratch.

## Required Outputs
Generate only documentation in `docs/conversion/`:
- `funnel_map.md`
- `friction_points.md`
- `copy_pack_ru_en.md`
- `cta_buttons.md`
- `experiments.md`

## Analysis Requirements
1. Map current conversion funnel from `/start` to:
- trial activation
- paid purchase/renewal
- first successful connection instruction screen

2. Identify conversion friction points:
- dead taps / unhandled or unclear CTA
- cognitive overload in copy
- missing recovery paths
- low-confidence payment/support moments

3. Provide RU/EN microcopy pack for highest-impact screens only.

4. Propose CTA labels and hierarchy that match existing callbacks.

5. Define practical A/B experiments with:
- hypothesis
- variant A/B
- success metric
- guardrails

## Constraints
- Documentation only.
- No business logic, payment, DB, key provisioning, or handler behavior changes in this step.
- Use only facts from current codebase.

## Severity
- P0: flow break with direct revenue/activation loss.
- P1: high drop-off risk or trust loss.
- P2: polish/consistency improvements.
