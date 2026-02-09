# Runbook

Common operations for running, restarting and debugging the VPNHub bot.

Start / stop (Docker Compose)

```bash
# start in background
docker-compose up -d

# stop
docker-compose down

# restart the bot service only
docker-compose restart bot
```

Run migrations

```bash
# run migrations (run.py executes alembic upgrade head on startup)
docker-compose exec bot bash -lc "python run.py"

# create new migration locally / in container
python bot/run.py --newmigrate "describe change"
```

View logs

```bash
# docker logs
docker-compose logs -f bot

# tail file logs (if running locally)
tail -f logs/all.log logs/errors.log
```

Debugging tips
- If startup fails with missing env variable, check `bot/bot/misc/util.py` — it validates required env vars and raises clear errors.
- To run quickly in debug mode, set `DEBUG=True` and app will use a local sqlite DB file `bot/database/DatabaseVPN.db`.
- Check NATS health endpoint (when running via Compose): `http://localhost:8222/varz` (or `http://nats:8222/varz` from inside containers).
- To inspect DB from host, connect to the `postgres` container or use psql against the `postgres_db_container` host defined in Compose.

Common checks when issues arise
- Verify `.env` contains correct PostgreSQL credentials and `PGADMIN_*` credentials.
- Confirm NATS is healthy and reachable.
- Check logs for stack traces and use `--newmigrate` flow only for creating migrations — do not create empty migrations.

Maintenance
- Backup the DB before running destructive migrations or schema changes.
- Monitor disk usage; the app logs are rotated, but containers may still fill volumes.
