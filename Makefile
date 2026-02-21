.PHONY: build up logs ps

build:
	docker compose build vpn_hub_bot

up:
	docker compose up -d vpn_hub_bot

logs:
	docker compose logs -f --tail=200 vpn_hub_bot

ps:
	docker compose ps
