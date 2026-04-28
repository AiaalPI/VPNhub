# RUNBOOK_INDEX

Индекс runbook-документов и когда какой использовать.

| File | Когда использовать |
|---|---|
| [docs/runbook.md](/Users/black/Projects/vpnhub/docs/runbook.md) | Базовые операционные действия: запуск/перезапуск, проверка логов, ресурсные лимиты, типовые диагностики. |
| [docs/ops/deploy_runbook.md](/Users/black/Projects/vpnhub/docs/ops/deploy_runbook.md) | Прод-деплой и gate-процедура (preflight/QA/smoke/triage), canonical deployment path. |
| [docs/ops/rollback_runbook.md](/Users/black/Projects/vpnhub/docs/ops/rollback_runbook.md) | Откат после неуспешного релиза и пост-проверки после rollback. |
| [docs/ops/backup_runbook.md](/Users/black/Projects/vpnhub/docs/ops/backup_runbook.md) | Резервное копирование PostgreSQL: ручной бэкап, cron/systemd timer, верификация и restore-подготовка. |
| [docs/ops/orchestrator_v3.md](/Users/black/Projects/vpnhub/docs/ops/orchestrator_v3.md) | Ручной/контролируемый orchestration-процесс для расследований и non-canonical ops задач. |
| [docs/ops/security_basics.md](/Users/black/Projects/vpnhub/docs/ops/security_basics.md) | Базовые требования безопасности и hygiene-практики при эксплуатации. |

## Связанные документы
- [AGENTS.md](/Users/black/Projects/vpnhub/AGENTS.md) — ограничения по деплою и CI
- [docs/project_rules.md](/Users/black/Projects/vpnhub/docs/project_rules.md) — проектные конвенции
