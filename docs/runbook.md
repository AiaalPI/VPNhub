# Runbook

Common operations for running, restarting and debugging the VPNHub bot.

---

## Resource Limits (P0.3)

**Why `mem_limit` / `cpus`, not `deploy.resources`:**
`deploy.resources` is a Docker Swarm field. Plain `docker compose up` silently ignores it —
no cgroup constraints are applied. The correct fields for non-Swarm Compose are
`mem_limit` and `cpus` at the service top level. These map directly to cgroup
`memory.limit_in_bytes` and `cpu.cfs_quota_us`.

Calibrated for a **4-vCPU / 8 GB RAM** host.

| Service | `cpus` | `mem_limit` |
|---|---|---|
| `vpn_hub_bot` | 2.0 | 1500m |
| `db_postgres` | 1.5 | 2000m |
| `nats` | 0.5 | 256m |
| `pgadmin` | 0.25 | 256m |
| `nats-migrate` | 0.5 | 256m |
| `nats-health` | 0.1 | 64m |

### Apply limits (force-recreate required)

`docker compose restart` does not re-apply resource constraints. Use:

```bash
docker compose up -d --force-recreate
```

### Verify limits are active

```bash
# Live stats — all containers
docker stats --no-stream

# Confirm enforced limits for a specific container
# Memory is returned in bytes; NanoCpus = cpu_count × 1_000_000_000
docker inspect vpn_hub_bot --format '{{.HostConfig.Memory}} {{.HostConfig.NanoCpus}}'
# Example output: 1572864000 2000000000
# → 1572864000 / 1024 / 1024 = 1500 MB, 2000000000 / 1e9 = 2.0 CPUs

docker inspect postgres_db_container --format '{{.HostConfig.Memory}} {{.HostConfig.NanoCpus}}'
# → 2097152000 / 1024 / 1024 = 2000 MB, 1500000000 / 1e9 = 1.5 CPUs
```

### Adjusting limits

Edit `mem_limit` / `cpus` for the relevant service in `docker-compose.yml`, then:

```bash
docker compose up -d --force-recreate <service_name>
```

### OOMKill diagnosis

```bash
docker inspect vpn_hub_bot | python3 -c "
import json, sys
s = json.load(sys.stdin)[0]['State']
print('OOMKilled:', s.get('OOMKilled'))
print('ExitCode: ', s.get('ExitCode'))
"
# Check kernel OOM log
dmesg | grep -i "oom\|killed" | tail -20
```
If `OOMKilled: true` → raise `mem_limit` for that service and force-recreate.

---

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

### Database migration conflicts / Alembic Drift Recovery

**Symptoms:**
- Logs show `DuplicateColumnError`, `column "X" of relation "Y" already exists`
- Logs show `alembic.error.CommandError` or `sqlalchemy.exc.ProgrammingError`
- Bot crash-loops immediately after deploy
- `alembic current` shows a revision behind `alembic heads`

**Root cause:** The live DB schema is ahead of (or mismatched with) what Alembic's
`alembic_version` table tracks. This commonly happens when a migration was applied
manually, a container crashed mid-migration, or columns were added outside Alembic.

---

#### Step 1 — Run the preflight drift checker (no DDL applied)

```bash
# From repo root (requires bot/.env or env vars set)
python scripts/alembic_preflight.py
```

Output will show:
- Current revision vs head revision
- Which tables have missing or extra columns
- Recommended action (stamp vs upgrade)

---

#### Step 2 — Check current alembic revision manually

```bash
# Inside the running bot container
docker compose exec vpn_hub_bot bash -c "cd /app && alembic -c bot/alembic.ini current"

# Or using a one-off container with the correct env
docker compose run --rm vpn_hub_bot bash -c "cd /app && alembic -c bot/alembic.ini current"
```

Check heads (what the code expects):
```bash
docker compose run --rm vpn_hub_bot bash -c "cd /app && alembic -c bot/alembic.ini heads"
```

Check full history:
```bash
docker compose run --rm vpn_hub_bot bash -c "cd /app && alembic -c bot/alembic.ini history --verbose"
```

---

#### Step 3 — Diagnose the specific drift scenario

**Scenario A: DB at head but columns still missing**
```bash
# Check if column actually exists in postgres
docker compose exec db_postgres psql -U $POSTGRES_USER -d $POSTGRES_DB \
  -c "\d users" | grep -E "trial_activated_at|trial_expires_at"
```
If column is missing: run upgrade (Step 4A).
If column exists but alembic thinks it's missing: stamp the correct revision (Step 4B).

**Scenario B: `DuplicateColumnError` on startup (crash-loop)**
```bash
# Verify column exists already
docker compose exec db_postgres psql -U $POSTGRES_USER -d $POSTGRES_DB \
  -c "SELECT column_name FROM information_schema.columns WHERE table_name='users' AND column_name='trial_activated_at';"
```
If column exists: schema is ahead. Stamp head without re-running DDL (Step 4B).

**Scenario C: alembic_version table is empty**
```bash
docker compose exec db_postgres psql -U $POSTGRES_USER -d $POSTGRES_DB \
  -c "SELECT * FROM alembic_version;"
```
Returns 0 rows → schema was created outside Alembic. Verify schema matches head,
then stamp (Step 4B).

---

#### Step 4A — DB behind Alembic: run upgrade

> Safe only when the column truly does NOT exist in the DB.
> Migrations `c8b1d5f0e3a4` and `ba7a3ffb8d04` are now idempotent — safe to re-run.

```bash
# Backup first (always)
docker compose exec db_postgres pg_dump -U $POSTGRES_USER $POSTGRES_DB > backup_$(date +%Y%m%d_%H%M%S).sql

# Run upgrade
docker compose run --rm vpn_hub_bot bash -c "cd /app && alembic -c bot/alembic.ini upgrade head"
```

---

#### Step 4B — DB ahead of Alembic: stamp without DDL

> Use when columns already exist but `alembic_version` is stale or empty.
> This records the revision WITHOUT running any DDL — no data risk.

```bash
# Replace <rev> with the correct revision (use `alembic heads` to get it)
docker compose run --rm vpn_hub_bot bash -c \
  "cd /app && alembic -c bot/alembic.ini stamp c8b1d5f0e3a4"

# Verify
docker compose run --rm vpn_hub_bot bash -c "cd /app && alembic -c bot/alembic.ini current"
```

Current head revision: **`c8b1d5f0e3a4`** (add_trial_timestamps_to_users, 2026-02-11).
Update this comment when new migrations are added.

---

#### Step 5 — Verify recovery and restart

```bash
# Confirm alembic version matches head
docker compose run --rm vpn_hub_bot bash -c "cd /app && alembic -c bot/alembic.ini current"

# Re-run preflight (should report no drift)
python scripts/alembic_preflight.py

# Restart bot
docker compose up -d vpn_hub_bot

# Watch logs for crash-loop (RestartCount should stay 0)
docker compose logs -f vpn_hub_bot --tail=50

# Confirm container is healthy (allow ~45s)
docker inspect --format='{{.State.Health.Status}}' vpn_hub_bot
# → healthy
```

---

#### Writing new migrations safely

When adding columns in future migrations, use the idempotent guard pattern:

```python
from sqlalchemy import inspect

def _column_exists(table: str, column: str) -> bool:
    bind = op.get_bind()
    insp = inspect(bind)
    return any(c["name"] == column for c in insp.get_columns(table))

def upgrade() -> None:
    with op.batch_alter_table('my_table', schema=None) as batch_op:
        if not _column_exists('my_table', 'new_column'):
            batch_op.add_column(sa.Column('new_column', sa.String(), nullable=True))
```

After adding a new migration, update the `EXPECTED_COLUMNS` dict in
`scripts/alembic_preflight.py` so the drift checker stays accurate.

---

## Distributed Lock (P0.4)

The bot uses a **NATS JetStream KV**-backed distributed lock to enforce single-instance
semantics across hosts and pods, replacing the previous `/tmp/vpnhub_bot.lock`
(`fcntl.flock`) approach that only worked on a single host.

### Design

| Property | Detail |
|---|---|
| Backend | NATS JetStream KV bucket `locks` |
| Lock key | `"bot-instance"` (one lock guards the entire bot process) |
| TTL | 60 s (renewed every 20 s via heartbeat task) |
| wait_timeout | 0 s (fail-fast: a second instance exits immediately if the lock is held) |
| Owner ID | `hostname:pid:uuid4` — unique per process instance |
| Acquire | `kv.create()` — atomic compare-and-set; only succeeds when key is absent |
| Steal | Only when `expires_at` has passed (stale lock from crashed process) |
| Release | Owner-checked `kv.delete()` — spurious releases silently ignored |

Lock module: [bot/bot/misc/distributed_lock.py](../bot/bot/misc/distributed_lock.py)

### Production verification (docker compose)

Run these commands in order after every deploy that touches lock or NATS config.

#### Step 1 — Confirm JetStream is enabled in NATS

```bash
# Check HTTP monitoring endpoint (no NATS CLI required)
curl -s http://127.0.0.1:8222/varz | python3 -c "
import json, sys
v = json.load(sys.stdin)
js = v.get('jetstream', {})
print('JetStream enabled :', js.get('config', {}).get('enabled', False))
print('Memory used       :', js.get('memory', 'n/a'))
print('Storage used      :', js.get('store_size', 'n/a'))
"
# Expected: JetStream enabled : True
```

#### Step 2 — Force-recreate containers and verify bot startup

```bash
docker compose up -d --force-recreate

# Tail logs until lock events appear (ctrl-c after seeing them)
docker compose logs -f vpn_hub_bot --tail=50
```

Expected log lines (in order):
```
event=startup.nats_connected servers=...
event=lock.acquire_attempt key=bot-instance ...
event=lock.acquired key=bot-instance owner=<hostname>:<pid>:<uuid>
event=startup.distributed_lock_acquired
event=scheduler.started
event=startup.polling_ready ...
```

#### Step 3 — Verify KV bucket exists (no NATS CLI required)

```bash
# Query JetStream stream list via HTTP — KV buckets are streams named KV_<bucket>
curl -s http://127.0.0.1:8222/jsz?streams=1 | python3 -c "
import json, sys
data = json.load(sys.stdin)
streams = data.get('account_details', [{}])[0].get('stream_detail', [])
kv = [s['config']['name'] for s in streams if s['config']['name'].startswith('KV_')]
print('KV buckets:', kv or '(none — bot not yet started)')
"
# Expected: KV buckets: ['KV_locks']
```

#### Step 4 — Confirm second instance fails loudly

```bash
# Start a second bot container — must exit non-zero within a few seconds
docker compose run --rm --name bot_second_instance vpn_hub_bot python run.py &
SECOND_PID=$!
sleep 10
wait $SECOND_PID
echo "Exit code: $?"   # must be non-zero (1 = lock held)

# Verify the log message
docker compose logs vpn_hub_bot 2>&1 | grep "distributed_lock_held"
# Expected:
#   CRITICAL ... event=startup.abort reason=distributed_lock_held hint=another_bot_instance_is_running
```

#### Step 5 — Run smoke test (all 4 scenarios)

```bash
# Run inside the bot container so it can reach NATS on the internal network
docker compose exec vpn_hub_bot python /app/scripts/lock_smoke_test.py \
  --nats-url nats://nats:4222
```

Expected output (exit 0):
```
RESULT: PASS — all assertions satisfied
  PASS  acquire_success
  PASS  fail_fast
  PASS  heartbeat_extends_ttl
  PASS  stale_lock_stealing
```

### Failure loudness guarantee

When the distributed lock is already held at startup, the bot:

1. Logs at **CRITICAL** level:
   ```
   event=startup.abort reason=distributed_lock_held hint=another_bot_instance_is_running
   ```
2. Exits with **code 1** (non-zero → Docker will mark the container as failed,
   triggering `restart: unless-stopped` backoff — it will not loop forever because
   NATS connect + lock-check is fast and the second instance exits before the TTL).

### Diagnose and recover stale lock

A stale lock occurs when the bot process is killed hard (SIGKILL, OOM) before the
heartbeat can renew. The lock TTL (60 s) clears it automatically. If you need to
recover immediately:

```bash
# Option A: wait 60 s (automatic — TTL expires, next start steals the lock)

# Option B: delete the lock key via the NATS HTTP API (no NATS CLI required)
# Note: this is a monitoring-only API; key deletion requires the NATS client.
# Use the bot container to delete it:
docker compose exec vpn_hub_bot python3 -c "
import asyncio, nats
async def run():
    nc = await nats.connect('nats://nats:4222')
    js = nc.jetstream()
    kv = await js.key_value('locks')
    await kv.delete('bot-instance')
    print('lock key deleted')
    await nc.close()
asyncio.run(run())
"

# Option C: if NATS CLI is installed
nats --server nats://127.0.0.1:4222 kv del locks bot-instance
```

After recovery, restart the bot:

```bash
docker compose up -d vpn_hub_bot
docker compose logs -f vpn_hub_bot --tail=20
# Look for: event=startup.distributed_lock_acquired
```

---

## Trial Period & Payment Flow

### Local Trial & Payment Testing

#### Unit Tests

Run trial + payment tests locally (no DB/NATS needed):

```bash
# install pytest and pytest-asyncio
pip install pytest pytest-asyncio

# run trial + payment tests
pytest tests/test_trial_payments.py -v

# run all tests
pytest tests/ -v
```

#### Manual Testing with Docker Compose

##### 1. Set up test environment

Add to `bot/.env`:
```bash
TRIAL_PERIOD=604800        # 7 days in seconds
FREE_SERVER=1              # Allow free VPN for trials
LIMIT_GB_FREE=10           # 10 GB limit for free/trial
```

##### 2. Start bot with test config

```bash
docker-compose up -d postgres nats bot
```

##### 3. Test trial activation flow

```bash
# Via bot handler (once implemented):
# /trial  -> grants 7-day trial key

# Or via direct DB (for testing):
docker-compose exec postgres psql -U $POSTGRES_USER -d $POSTGRES_DB <<EOF
  -- Create test user
  INSERT INTO users (tgid, username, banned, trial_period, lang)
  VALUES (123456789, 'testuser', false, false, 'en');
  
  -- Activate trial (see bot/bot/service/trial_service.py)
  UPDATE users
  SET trial_period=true, trial_activated_at=now(), trial_expires_at=now() + interval '7 days'
  WHERE tgid=123456789;
  
  -- Create trial key (7 days = 604800 sec)
  INSERT INTO keys (user_tgid, subscription, trial_period, free_key)
  VALUES (123456789, EXTRACT(EPOCH FROM now() + interval '7 days')::bigint, true, false);
EOF
```

##### 4. Test payment webhook (Cryptomus example)

Simulate webhook from Cryptomus locally:

```bash
# In Python shell or test script:

import asyncio
import json
from httpx import AsyncClient

webhook_payload = {
    'uuid': 'test-uuid-123',
    'order_id': '123456789_1707123456_1',  # user_id_timestamp_months
    'status': 'paid',
    'amount': '100.00'
}

# To test locally, call the handler directly:
from bot.handlers.payment_webhook import handle_cryptomus_webhook
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

# Set up real session if testing with DB
engine = create_async_engine('postgresql+asyncpg://user:pass@localhost/vpnhub_db')
async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

async def test():
    async with async_session() as session:
        result = await handle_cryptomus_webhook(session, webhook_payload)
        print(f"Webhook processed: {result}")

asyncio.run(test())
```

#### Webhook Idempotency Testing

Replaying the same webhook twice should result in idempotent behavior:

```bash
# Send webhook twice with same order_id
curl -X POST http://localhost:8000/webhook/cryptomus \
  -H "Content-Type: application/json" \
  -d '{"order_id": "123_1707123456_1", "status": "paid", "amount": "100"}'

curl -X POST http://localhost:8000/webhook/cryptomus \
  -H "Content-Type: application/json" \
  -d '{"order_id": "123_1707123456_1", "status": "paid", "amount": "100"}'

# Both should succeed; payment should only be applied once
# Check logs: second call should show "duplicate action=idempotent"
```

### Subscription Lifecycle Operations

#### Extend Subscription (Admin/Payment)

```bash
# Via function (in handler or background job):
from bot.service.subscription_service import extend_subscription

# Extend user 123456789 by 30 days
result = await extend_subscription(
    user_id=123456789,
    days=30,
    reason='payment:cryptomus',
    session=session,
    id_payment='order_id_from_payment_provider'
)

# Logs will show subscription extension with old/new expiry times
```

#### Check Trial Expiry (Background Job)

The `loop()` background job runs every minute and:
1. Checks all subscriptions for expiry → deletes expired keys
2. Checks all active trials for expiry → marks trial as expired
3. Sends user notification for both cases

**To view trial expiry logs:**

```bash
docker-compose logs bot | grep "event=trial_expiry"
```

#### Database Queries

Find users with trials:

```bash
docker-compose exec postgres psql -U $POSTGRES_USER -d $POSTGRES_DB <<EOF
  SELECT tgid, trial_period, trial_activated_at, trial_expires_at
  FROM users
  WHERE trial_period = true
  ORDER BY trial_activated_at DESC;
EOF
```

Find pending payments:

```bash
docker-compose exec postgres psql -U $POSTGRES_USER -d $POSTGRES_DB <<EOF
  SELECT id, user, id_payment, status, amount, data
  FROM payments
  WHERE status IN ('pending', 'failed')
  ORDER BY data DESC;
EOF
```

Find orphaned keys (key without payment):

```bash
docker-compose exec postgres psql -U $POSTGRES_USER -d $POSTGRES_DB <<EOF
  SELECT k.id, k.user_tgid, k.subscription, k.id_payment
  FROM keys k
  LEFT JOIN payments p ON k.id_payment = p.id_payment
  WHERE k.id_payment IS NOT NULL AND p.id IS NULL;
EOF
```

### Troubleshooting Trial/Payment Issues

#### Trial not activating

**Symptoms:** User calls `/trial`, flag is set but key is not created.

**Diagnosis:**

Check logs for:
```bash
docker-compose logs bot | grep "event=trial_activation"
```

Verify user eligibility:
```bash
docker-compose exec postgres psql -U $POSTGRES_USER -d $POSTGRES_DB <<EOF
  SELECT tgid, trial_period, banned, (SELECT COUNT(*) FROM keys WHERE user_tgid=users.tgid AND subscription > EXTRACT(EPOCH FROM now())::bigint) as active_keys
  FROM users
  WHERE tgid = 123456789;
EOF
```

**Solution:**
- User in trial already? `trial_period = true`
- User banned? `banned = true` → Admin must unban
- User has active paid key? Check `keys` table for subscription > now

#### Payment webhook not confirmed

**Symptoms:** Payment shows in logs but doesn't extend subscription.

**Diagnosis:**

Check webhook logs:
```bash
docker-compose logs bot | grep "event=cryptomus_webhook"
```

Verify payment in DB:
```bash
docker-compose exec postgres psql -U $POSTGRES_USER -d $POSTGRES_DB <<EOF
  SELECT id, id_payment, status, amount FROM payments WHERE id_payment LIKE '%order_id%';
EOF
```

**Solution:**
- Payment status = 'pending'? Webhook not confirmed yet
- Payment status = 'failed'? Check error in logs
- Order ID format wrong? Should be `user_id_timestamp_months`

#### Duplicate payment applied

**Symptoms:** User charged twice for same order.

**Diagnosis:**

Verify idempotency logic is working:
```bash
docker-compose logs bot | grep -A2 "duplicate action=idempotent"
```

**Solution:**
Idempotency is automatic. Each payment order_id is unique per payment attempt. If user retries payment:
1. New order_id is issued
2. New payment entry is created
3. Subscription is extended again

This is expected behavior (user can pay multiple times to extend further).

If duplicate extension for same payment: manually revert in DB:
```bash
docker-compose exec postgres psql -U $POSTGRES_USER -d $POSTGRES_DB <<EOF
  -- Find key and restore old expiry
  UPDATE keys
  SET subscription = <old_expiry_timestamp>
  WHERE id = <key_id>;
  
  -- Mark payment as failed to prevent duplicate
  UPDATE payments
  SET status = 'failed'
  WHERE id_payment = '<order_id>';
EOF
```

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