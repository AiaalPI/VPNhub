# VPNHub AI Release Train (ART) — Overview

## Goal
Establish a predictable, automated delivery loop where AI agents:
- Maintain a high-quality backlog (Issues + Project).
- Drive work through PRs with QA gates.
- Produce release notes and changelog entries.
- Monitor production signals and open follow-up issues.

This system is designed to increase delivery velocity without sacrificing safety.

## System Of Record
- Work items: GitHub Issues (every change maps to an issue).
- Workflow state: GitHub Project "VPNHub AI Control".
- Release cadence: Sprint-based (2 weeks) + patch releases as needed.
- Source of truth for runtime: `docker compose` build + smoke.

## Roles (AI + Humans)
- PM Agent: clarifies problem, writes acceptance criteria, prioritizes.
- Dev Agent: implements minimal change set, opens PR, links issue.
- QA Agent: runs deterministic checks, blocks on P0/P1 regressions.
- SRE Agent: validates health, deploy, triage, and rollback playbooks.
- Release Agent: cuts release, generates notes, coordinates smoke checks.
- Growth Agent: ships copy/CTA experiments, measures funnel metrics.

Humans own final approvals for:
- Secrets rotation
- Production deploy
- Rollbacks
- Payment/provider changes

## Release Train Rules
- No work without an issue.
- Every PR references an issue and a sprint milestone.
- P0/P1 requires smoke + triage gates before "Released".
- "Monitoring" column must be used for post-release observation.

## Operating Loop
Daily:
1. Triage production signals -> create/label issues.
2. Pull top issues from Ready -> In Progress.
3. Ensure CI green and backlog remains groomed.

Per sprint:
1. Plan sprint scope (P0/P1 first).
2. Execute PRs with tight acceptance criteria.
3. Release with automated notes + smoke checks.
4. Monitor; open follow-up issues if signals degrade.

## Implementation References
- Orchestrator gates: `scripts/orchestrate_v3.sh`
- QA callback audit: `scripts/qa/check_callbacks.py`
- Analytics events (if present): `docs/analytics/funnel_events.md`

