# GitHub Setup — VPNHub AI Release Train

This file is the canonical checklist to set up GitHub Issues + Projects for the AI Release Train.

## Step 1: Create GitHub Project (manual)
Create a GitHub Project named: `VPNHub AI Control`

Columns:
- Backlog
- Ready
- In Progress
- In Review
- Blocked
- Done
- Released
- Monitoring

Notes:
- Use Project as the workflow state machine.
- Issues remain the system of record for work.

## Step 2: Labels
Create labels (exact):
- `P0`
- `P1`
- `P2`
- `epic`
- `infra`
- `growth`
- `china`
- `failover`
- `ux`
- `ai-agent`
- `bug`
- `tech-debt`
- `release-train`

## Step 3: Milestones
Create milestones:
- `Sprint 1`
- `Sprint 2`
- `Sprint 3`
- `Sprint 4`
- `Release v1.0`
- `Release v1.1`

## Optional: Create via GitHub CLI (`gh`)
If you want automation, install GitHub CLI and authenticate:

```bash
brew install gh
gh auth login
```

Then run sprint planning in dry-run mode (prints commands):

```bash
DRY_RUN=1 ./scripts/release_train/sprint_planning.sh "Sprint 1"
```

Apply mode (creates labels/milestone/issues):

```bash
DRY_RUN=0 ./scripts/release_train/sprint_planning.sh "Sprint 1"
```

Limitations:
- This repository does not include automated GitHub Project v2 creation (requires GraphQL + org/project IDs).
- The script covers labels, milestones, and issue creation.

