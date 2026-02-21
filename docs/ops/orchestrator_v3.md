# Orchestrator V3 FULL

Strict deployment pipeline with hard gates:

0. Git Clean Guard (exit 3)
1. Preflight secret scan (exit 2/1)
2. QA (exit 4)
3. Branch sync + push
4. Deploy via SSH (exit 5)
5. Smoke checks (exit 6 or 2 for conflict)
6. Triage with P0/P1/P2 classification (exit 7 on P0/P1)
7. Hard gates evaluation
8. Auto taskpack generation when failing
9. Final report `.artifacts/report.md`

Run:

```bash
./scripts/orchestrate_v3.sh --host r1105660 --branch <branch>
```
