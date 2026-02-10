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