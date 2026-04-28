# CONTEXT_INDEX (AI)

Порядок чтения контекста для AI/Codex и карта source-of-truth.

## Рекомендуемый порядок чтения
1. [AGENTS.md](/Users/black/Projects/vpnhub/AGENTS.md)
2. [PROJECT_CONTEXT.md](/Users/black/Projects/vpnhub/PROJECT_CONTEXT.md)
3. [README.md](/Users/black/Projects/vpnhub/README.md)
4. [docs/architecture.md](/Users/black/Projects/vpnhub/docs/architecture.md)
5. [docs/env.md](/Users/black/Projects/vpnhub/docs/env.md)
6. [NODES.md](/Users/black/Projects/vpnhub/NODES.md)
7. [RUNBOOK_INDEX.md](/Users/black/Projects/vpnhub/RUNBOOK_INDEX.md)
8. [docs/runbook.md](/Users/black/Projects/vpnhub/docs/runbook.md)
9. [docs/ops/deploy_runbook.md](/Users/black/Projects/vpnhub/docs/ops/deploy_runbook.md)
10. [Obsidian kynvpn/atlas/архитектура системы.md](/Users/black/Projects/vpnhub/Obsidian%20kynvpn/atlas/%D0%B0%D1%80%D1%85%D0%B8%D1%82%D0%B5%D0%BA%D1%82%D1%83%D1%80%D0%B0%20%D1%81%D0%B8%D1%81%D1%82%D0%B5%D0%BC%D1%8B.md)
11. [Obsidian kynvpn/atlas/схема базы данных.md](/Users/black/Projects/vpnhub/Obsidian%20kynvpn/atlas/%D1%81%D1%85%D0%B5%D0%BC%D0%B0%20%D0%B1%D0%B0%D0%B7%D1%8B%20%D0%B4%D0%B0%D0%BD%D0%BD%D1%8B%D1%85.md)
12. [Obsidian kynvpn/sessions/2026-04-21 аудит Finnish сервера и оптимизация.md](/Users/black/Projects/vpnhub/Obsidian%20kynvpn/sessions/2026-04-21%20%D0%B0%D1%83%D0%B4%D0%B8%D1%82%20Finnish%20%D1%81%D0%B5%D1%80%D0%B2%D0%B5%D1%80%D0%B0%20%D0%B8%20%D0%BE%D0%BF%D1%82%D0%B8%D0%BC%D0%B8%D0%B7%D0%B0%D1%86%D0%B8%D1%8F.md)

## Source of Truth (по зонам)

### Runtime и правила выполнения
- [AGENTS.md](/Users/black/Projects/vpnhub/AGENTS.md)
- [docs/project_rules.md](/Users/black/Projects/vpnhub/docs/project_rules.md)

### Архитектура и компоненты
- [docs/architecture.md](/Users/black/Projects/vpnhub/docs/architecture.md)
- [README.md](/Users/black/Projects/vpnhub/README.md)

### Конфигурация среды
- [docs/env.md](/Users/black/Projects/vpnhub/docs/env.md)

### Операции и инциденты
- [RUNBOOK_INDEX.md](/Users/black/Projects/vpnhub/RUNBOOK_INDEX.md)
- [docs/runbook.md](/Users/black/Projects/vpnhub/docs/runbook.md)
- [docs/ops/*](/Users/black/Projects/vpnhub/docs/ops/deploy_runbook.md)

### Ноды и VPN-панели
- [NODES.md](/Users/black/Projects/vpnhub/NODES.md)
- [Obsidian kynvpn/atlas/схема базы данных.md](/Users/black/Projects/vpnhub/Obsidian%20kynvpn/atlas/%D1%81%D1%85%D0%B5%D0%BC%D0%B0%20%D0%B1%D0%B0%D0%B7%D1%8B%20%D0%B4%D0%B0%D0%BD%D0%BD%D1%8B%D1%85.md)
- [Obsidian kynvpn/knowledge/integrations/Marzban VPN.md](/Users/black/Projects/vpnhub/Obsidian%20kynvpn/knowledge/integrations/Marzban%20VPN.md)
- [Obsidian kynvpn/knowledge/integrations/VLESS + Reality через 3x-UI.md](/Users/black/Projects/vpnhub/Obsidian%20kynvpn/knowledge/integrations/VLESS%20%2B%20Reality%20%D1%87%D0%B5%D1%80%D0%B5%D0%B7%203x-UI.md)

## Правила интерпретации для AI
- Если данные расходятся между документами, приоритет: `AGENTS.md` > `docs/*` > Obsidian session notes.
- Если поле не подтверждено явно, использовать `TODO` и не выдумывать значения.
- Для операционных решений проверять дату документа (`last verified`) перед действием.
