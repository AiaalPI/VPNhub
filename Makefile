.PHONY: build up logs ps preflight qa orchestrate-v3 deploy-v3 smoke-v3 triage-v3 report-v3

build:
	docker compose build vpn_hub_bot

up:
	docker compose up -d vpn_hub_bot

logs:
	docker compose logs -f --tail=200 vpn_hub_bot

ps:
	docker compose ps

preflight:
	./scripts/preflight.sh

qa:
	./scripts/qa.sh

orchestrate-v3:
	./scripts/orchestrate_v3.sh --host $(HOST) --branch $(BRANCH)

deploy-v3:
	./scripts/deploy_git.sh --host $(HOST) --branch $(BRANCH)

smoke-v3:
	./scripts/smoke.sh --host $(HOST)

triage-v3:
	./scripts/triage.sh --host $(HOST) --branch $(BRANCH)

report-v3:
	./scripts/report.sh
