# Backlog Policy (GitHub Issues + Projects)

## Issue Taxonomy
Labels:
- Priority: `P0`, `P1`, `P2`
- Type: `bug`, `tech-debt`, `infra`, `growth`, `ux`, `china`, `failover`, `ai-agent`, `release-train`
- Grouping: `epic`

Milestones:
- `Sprint 1..4`
- `Release v1.0`, `Release v1.1`

## Definition of Done (DoD)
Every issue done means:
- Code merged (PR linked).
- Tests/QA gates executed.
- Deploy completed (if relevant).
- Monitoring signal checked.
- Docs updated if behavior changes.

## WIP Limits
- In Progress: max 5 issues total
- In Review: max 5 PRs
- Blocked: must have explicit blocker text + owner

## Priority Rules
- P0: production incident / security / revenue loss; interrupts sprint.
- P1: high confusion / conversion drop / scalability blocker.
- P2: polish and optimizations; scheduled if capacity.

