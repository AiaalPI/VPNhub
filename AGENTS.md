# Agent Rules

> **Master agent taxonomy for VPNHub.** Three models coexist: (1) CI rules below, (2) active doc-generating agents, (3) planned Release Train roles. Only models 1 and 2 are currently operational.

## CI / Human Agent Rules

- Work only through branch + Pull Request. Do not push directly to `main`.
- Never commit secrets or local env files (`bot/.env`, `.env`).
- Before opening/updating PR, run `docker compose build vpn_hub_bot` and ensure it passes.
- Production deployment is allowed only through GitHub Actions and `/opt/vpnhub/deploy.sh` on server.

---

## Current Agent Capabilities

> Source: `AI_AGENTS_ANALYSIS.md` (2026-02-24). Status: all agents are **documentation-generators only** — they read code and produce docs. No agent autonomously modifies code.

### Active Documentation Agents (LLM-based)

| Agent | Input Spec | Output Location | Status |
|---|---|---|---|
| **UX Audit Agent** | `docs/ai-release-train/briefs/UX_AUDIT_BRIEF.md` | `docs/ux/` | Active |
| **QA Flow Agent** | `docs/ai-release-train/briefs/QA_AGENT_BRIEF.md` | `docs/qa/` | Active |
| **Conversion Agent** | `docs/ai-release-train/briefs/CONVERSION_AGENT_BRIEF.md` | `docs/conversion/` | Active |

### Automation Scripts (Non-LLM, Active)

| Script | Role | Integrated Into |
|---|---|---|
| `scripts/qa/check_callbacks.py` | AST callback coverage checker | `scripts/qa.sh`, CI gate |
| `scripts/orchestrate_v3.sh` | Full deploy pipeline with hard gates | GitHub Actions |
| `bot/bot/middlewares/conversion_events.py` | Passive funnel event tracking | Production bot |

### Readiness Summary

| Capability | Status |
|---|---|
| Documentation generation | Operational — 100% |
| Automated QA validation | Operational — 90% |
| Autonomous code changes | Not implemented — 0% |
| Real-time monitoring/intelligence | Not implemented — 0% |

---

## Planned Release Train Roles (Aspirational — Not Yet Implemented)

> Defined in `docs/ai-release-train/release_train_overview.md`. These describe a future operating model. None are currently executing.

| Role | Spec File |
|---|---|
| PM Agent | `docs/ai-release-train/agents/pm_agent.md` |
| Dev Agent | `docs/ai-release-train/agents/dev_agent.md` |
| QA Agent | `docs/ai-release-train/agents/qa_agent.md` |
| SRE Agent | `docs/ai-release-train/agents/sre_agent.md` |
| Release Agent | `docs/ai-release-train/agents/release_agent.md` |
| Growth Agent | `docs/ai-release-train/agents/growth_agent.md` |

Human approvals required for: secrets rotation, production deploys, rollbacks, payment/provider changes.
