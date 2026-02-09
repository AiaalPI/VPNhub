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
## Common Failure Scenarios

### Container crashes immediately on startup
**Symptoms:** `docker-compose logs bot` shows immediate exit, no error visible.

**Diagnosis:**
1. Check for Python syntax errors: `python3 -m py_compile bot/bot/*.py`
2. Verify env vars are loaded: `grep -E '^(TG_TOKEN|POSTGRES_USER|NATS_SERVERS)=' bot/.env`
3. Check required fields exist in `Config` (see `bot/bot/misc/util.py`)

**Solution:**
- Ensure `bot/.env` exists and has all required fields listed in `docs/env.md`
- Verify PostgreSQL container is running: `docker-compose ps postgres`
- Check NATS container is running: `docker-compose ps nats`
- View full startup logs: `docker-compose logs --tail=100 bot`

### Missing .mo locale files (translation error)
**Symptoms:** `FileNotFoundError: *.mo` or untranslated text appears in chat.

**Diagnosis:**
Check locale files exist: `ls -la bot/bot/locale/*/`

**Solution:**
Rebuild bot image to recompile translations:
```bash
docker-compose build bot
docker-compose up -d bot
```

### Invalid TG_TOKEN (Telegram API rejects)
**Symptoms:** Logs show `Unauthorized` from Telegram, or bot never accepts messages.

**Diagnosis:**
Test token: `curl -X GET "https://api.telegram.org/bot<TOKEN>/getMe"` (should return user info, not 404/401)

**Solution:**
1. Verify token in `bot/.env` is correct and complete (40+ chars)
2. Regenerate token if compromised: 
   - Message BotFather on Telegram
   - Select bot → Edit Bot → Edit token
   - Update `TG_TOKEN` in `bot/.env`
3. Restart: `docker-compose restart bot`

### PostgreSQL authentication failed
**Symptoms:** Logs show `FATAL: password authentication failed` or `connection refused`.

**Diagnosis:**
```bash
# Try connecting from postgres container
docker-compose exec postgres psql -U $POSTGRES_USER -d $POSTGRES_DB -c "SELECT 1"
```

**Solution:**
1. Check `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` in `bot/.env`
2. Ensure these match the postgres service env vars in `docker-compose.yml`
3. Reset DB (destructive): `docker-compose down -v && docker-compose up -d`

### NATS stream not found / consumer error
**Symptoms:** Logs show `stream not found` or `consumer subscribe failed`.

**Diagnosis:**
Check NATS streams: `docker-compose exec nats nats stream ls`

**Solution:**
1. Run migration to create streams: `docker-compose exec bot python run.py`
2. Check NATS health: `curl http://localhost:8222/varz | jq .streaming`
3. Verify `NATS_SERVERS` in `bot/.env` (default: `nats://nats:4222`)
4. If NATS container crashed: `docker-compose logs nats | tail -50`

### Server check timeout loop (high CPU)
**Symptoms:** Bot CPU spikes, many `timeout` logs in quick succession.

**Diagnosis:**
```bash
docker-compose logs bot | grep "event=server_check status=timeout" | wc -l
```

**Solution:**
1. Increase timeout threshold: `SERVER_CHECK_TIMEOUT_SEC=15` in `bot/.env` (default 8)
2. Reduce concurrency: `SERVER_CHECK_CONCURRENCY=2` in `bot/.env` (default 5)
3. Check VPN servers are responding: try SSH/ping to server IPs
4. Verify network connectivity from bot container: `docker-compose exec bot ping <server_ip>`

### Admin alerts not sent (throttled silently)
**Symptoms:** Expected server failure/recovery alerts don't arrive, but logs show `admin_alert_suppressed`.

**Diagnosis:**
This is expected after 1 alert per 3600 seconds (1 hour) per server. Check logs:
```bash
docker-compose logs bot | grep admin_alert_suppressed
```

**Solution:**
To force alert (dev/test only): temporarily reduce `can_send_alert()` cooldown in `bot/bot/misc/util.py` or delete `_alert_throttle` dict at runtime.
For production: wait 1 hour between similar alerts per server.

### Database migration conflicts
**Symptoms:** Logs show `alembic.error.CommandError` or `sqlalchemy.exc.ProgrammingError`.

**Diagnosis:**
Check current migration state:
```bash
docker-compose exec bot bash -lc "python -c \"from alembic import command; from alembic.config import Config; c = Config('bot/alembic.ini'); command.current(c)\""
```

**Solution:**
1. Backup DB: `docker-compose exec postgres pg_dump -U $POSTGRES_USER $POSTGRES_DB > backup.sql`
2. Do not create empty migrations manually
3. Use `python run.py --newmigrate "description"` for new migrations
4. Re-run migrations: `docker-compose restart bot`