# UX Audit Brief — VPNHub Telegram Bot

## Product Context

VPNHub is a Telegram bot that provides VPN access via subscription.
Core value: user gets a working VPN connection as fast as possible.

Main product mechanics:
- User onboarding via /start
- Subscription plans (buy / renew)
- VPN keys / configuration delivery
- Device connection instructions
- Referral system
- Support / FAQ
- Subscription status tracking (active / expired / trial)

Primary goal:
User connects to VPN in under 60 seconds after /start.

---

# Audit Goal

Analyze the CURRENT UX implemented in the repository.

Do NOT redesign from scratch.
Map what actually exists in the code:
- Handlers
- Callback routes
- FSM states
- Button layouts
- Messages
- Error states

Then produce:
- UX map
- Issues with severity
- Concrete fixes with file references

---

# What To Analyze

## 1. Entry & Onboarding
- /start behavior
- First screen content
- Is value proposition clear?
- Is next step obvious?

## 2. Main Menu Structure
- Menu hierarchy
- Button naming consistency
- Reply vs inline keyboard usage
- Navigation clarity

## 3. Core Flow: Get Connected
- How user gets VPN key
- How instructions are delivered
- iOS / Android / Windows flows
- How many clicks to "connected"
- Are there dead ends?

## 4. Subscription Flow
- Plan selection UX
- Pricing clarity
- Renewal UX
- Expired subscription handling
- Payment failure handling

## 5. Referral Flow
- Where referral is shown
- Is reward clear?
- Is share action easy?

## 6. Support / FAQ
- Is help accessible from anywhere?
- Are common issues covered?
- Is admin contact clear?

## 7. Edge Cases
- No subscription
- Expired subscription
- No keys available
- Payment failed
- User banned
- Backend error
- Slow loading / waiting state

## 8. Navigation Consistency
- Always have Back?
- Always have Main menu?
- Any loops?
- Any screen without exit?

---

# UX Success Criteria

A good VPNHub UX must:

- Minimize time-to-value
- Never trap user in dead end
- Always provide next action
- Avoid long paragraphs
- Keep screens <= 6 lines
- Use clear CTA buttons
- Provide recovery paths

---

# Required Output

## 1. AS-IS UX Map

For each screen:
- Screen name
- Trigger (command/callback)
- Message text
- Buttons (label + callback_data)
- Next transitions
- Exit paths

Save to:
docs/ux/as_is_map.md

---

## 2. Audit Findings

For each issue:
- Severity:
  - P0 = user stuck / broken
  - P1 = high confusion / drop-off risk
  - P2 = polish / clarity issue
- File path
- Handler/function
- Description
- Why it matters
- Proposed fix

Save to:
docs/ux/audit_findings.md

---

## 3. Fix Plan (Prioritized)

- Minimal-impact changes first
- Quick UX wins
- Copy improvements
- Button restructuring
- Navigation fixes

Include:
- Before / After text
- Before / After button layout

Save to:
docs/ux/fix_plan.md

---

## 4. Optional: Conversion Optimization Ideas

Suggest:
- Onboarding improvements
- Microcopy improvements
- CTA optimization
- Reducing friction in subscription

Save to:
docs/ux/optimization.md

---

# Constraints

- Do not modify business logic unless absolutely required.
- Do not remove features.
- Keep current architecture.
- Focus on UX clarity and conversion.
- No theoretical essays — concrete actionable output.

---

# Priority Focus

The most critical flow to audit first:

/start → subscription check → get VPN key → connection instructions → connected

If this flow is not frictionless, mark as P0/P1.

---

# Final Deliverable

After analysis, provide:

- Top 10 UX problems
- Quick wins list
- Estimated UX impact of each fix
- Suggested implementation order