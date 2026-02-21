# Agent Rules

- Work only through branch + Pull Request. Do not push directly to `main`.
- Never commit secrets or local env files (`bot/.env`, `.env`).
- Before opening/updating PR, run `docker compose build vpn_hub_bot` and ensure it passes.
- Production deployment is allowed only through GitHub Actions and `/opt/vpnhub/deploy.sh` on server.
