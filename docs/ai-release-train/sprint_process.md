# Sprint Process (AI Release Train)

## Sprint Cadence
- Duration: 2 weeks
- Milestone: `Sprint N`
- Scope: prioritized P0/P1, limited WIP, measurable outcomes.

## Sprint Planning (Day 1)
Inputs:
- Current production signals (errors, restarts, conversion drop).
- Backlog priorities (P0->P2).
- Roadmap focus (growth/ux/china/failover).

Outputs:
- Sprint milestone with issue list and ownership.
- Project board updated:
  - Backlog -> Ready for committed scope
  - Non-committed stays in Backlog

Definition of Ready (Issue):
- Clear title and description.
- Acceptance Criteria measurable.
- Dependencies explicit.
- Risk noted (data loss / payments / security).

## Execution (Days 2–10)
Rules:
- 1 PR = 1 issue (or a small stack, explicitly linked).
- PR must pass:
  - `python -m compileall -q bot`
  - `pytest -q` (if tests exist)
  - `docker compose build vpn_hub_bot`
- P0/P1 PRs require explicit smoke checklist in PR description.

## Sprint Review (Day 10)
Deliverables:
- Release notes draft.
- "Done" issues moved to "Released" only after deploy + smoke.

## Retrospective (Day 10)
Capture:
- Lead time by priority.
- Defect escape rate (post-release incidents).
- Funnel changes (trial->paid, pay success, MTFC).

