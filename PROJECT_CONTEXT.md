# PROJECT_CONTEXT

## Что это за проект
KYNVPN (VPNHub / Lumen Connect) — Telegram-бот для выдачи и управления VPN-подписками.

Подтверждено документами:
- [README.md](/Users/black/Projects/vpnhub/README.md)
- [docs/architecture.md](/Users/black/Projects/vpnhub/docs/architecture.md)
- [Obsidian kynvpn/00-home/index.md](/Users/black/Projects/vpnhub/Obsidian%20kynvpn/00-home/index.md)

## Технический стек
- Python 3.11+, `aiogram`, `FastAPI`, `SQLAlchemy`, `Alembic`
- PostgreSQL
- Redis (FSM/state)
- NATS JetStream + отдельный worker
- Docker Compose
- VPN backends/panels: 3x-ui (VLESS/Reality), Marzban, Remnawave, Outline, WireGuard/AWG

Источники:
- [README.md](/Users/black/Projects/vpnhub/README.md)
- [bot/requirements.txt](/Users/black/Projects/vpnhub/bot/requirements.txt)
- [Obsidian kynvpn/atlas/архитектура системы.md](/Users/black/Projects/vpnhub/Obsidian%20kynvpn/atlas/%D0%B0%D1%80%D1%85%D0%B8%D1%82%D0%B5%D0%BA%D1%82%D1%83%D1%80%D0%B0%20%D1%81%D0%B8%D1%81%D1%82%D0%B5%D0%BC%D1%8B.md)
- [Obsidian kynvpn/knowledge/integrations/VLESS + Reality через 3x-UI.md](/Users/black/Projects/vpnhub/Obsidian%20kynvpn/knowledge/integrations/VLESS%20%2B%20Reality%20%D1%87%D0%B5%D1%80%D0%B5%D0%B7%203x-UI.md)
- [Obsidian kynvpn/knowledge/integrations/Marzban VPN.md](/Users/black/Projects/vpnhub/Obsidian%20kynvpn/knowledge/integrations/Marzban%20VPN.md)

## Ключевые папки проекта
- `bot/` — основной код бота
- `bot/bot/handlers/` — Telegram handlers (тонкий слой)
- `bot/bot/services/` — бизнес-логика
- `bot/bot/database/` — модели и доступ к БД
- `bot/bot/misc/VPN/` — адаптеры VPN-протоколов/панелей
- `bot/bot/misc/Payment/` — адаптеры оплат
- `docs/` — техническая и операционная документация
- `Obsidian kynvpn/` — knowledge vault (память проекта)

Источники:
- [README.md](/Users/black/Projects/vpnhub/README.md)
- [docs/architecture.md](/Users/black/Projects/vpnhub/docs/architecture.md)

## Канонические документы (для работы AI)
1. [AGENTS.md](/Users/black/Projects/vpnhub/AGENTS.md) — правила и роль агента, ограничения CI/деплоя
2. [README.md](/Users/black/Projects/vpnhub/README.md) — обзор продукта и структуры
3. [docs/architecture.md](/Users/black/Projects/vpnhub/docs/architecture.md) — high-level архитектура
4. [docs/env.md](/Users/black/Projects/vpnhub/docs/env.md) — env-контракт
5. [docs/runbook.md](/Users/black/Projects/vpnhub/docs/runbook.md) + `docs/ops/*` — эксплуатация
6. [Obsidian kynvpn/atlas/*](/Users/black/Projects/vpnhub/Obsidian%20kynvpn/atlas/архитектура%20системы.md) — актуальные внутренние знания по архитектуре/БД/стеку

## Правила для AI/Codex (кратко)
- Не коммитить секреты и `.env`
- Не пушить напрямую в `main` (через branch + PR)
- Перед PR: `docker compose build vpn_hub_bot`
- Прод-деплой только через GitHub Actions + `/opt/vpnhub/deploy.sh`
- Любые изменения, влияющие на эксплуатацию, отражать в `docs/` и/или Obsidian vault

Источник:
- [AGENTS.md](/Users/black/Projects/vpnhub/AGENTS.md)

## Пробелы контекста
- `PROJECT_CONTEXT.md` ранее отсутствовал (создан как черновик)
- `ARCHITECTURE.md` в корне отсутствует (есть [docs/architecture.md](/Users/black/Projects/vpnhub/docs/architecture.md))
- `NODES.md` ранее отсутствовал (создан как черновик)
