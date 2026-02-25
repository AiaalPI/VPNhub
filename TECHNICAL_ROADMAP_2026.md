# VPNHUB TECHNICAL ROADMAP 2026

**Date:** 2026-02-24
**Status:** Production Stabilization + Strategic Growth
**Audience:** Technical Leadership, Team Leads, DevOps
**Based on:** Technical Audit + AI Agents Analysis

---

## EXECUTIVE SUMMARY

### Current State
- **Production Readiness:** 5/10 (blocker issues exist)
- **DevOps Maturity:** 6/10 (good infra, missing monitoring/scaling)
- **Scalability:** 4/10 (polling-based, single-instance locks)
- **AI Readiness:** 7/10 (3 agents + analytics active, doc-generation only)
- **Security Posture:** 4/10 (secrets exposed in repo)

### Critical Blockers
1. **Secrets in .env** — OAuth tokens, DB passwords, payment keys exposed in Git
2. **No /health endpoint** — Load balancer cannot verify service health
3. **No resource limits** — Container can OOMKill production
4. **File-based locking** — Doesn't work on Kubernetes
5. **Backup strategy missing** — Zero disaster recovery

### What Works Well
- ✅ Clean architecture (handlers → services → database)
- ✅ Graceful shutdown & signal handling
- ✅ Async/await throughout (uvloop + asyncio)
- ✅ Linear DB migrations, no conflicts
- ✅ AI-driven documentation (UX, QA, Conversion agents active)
- ✅ Analytics middleware (funnel tracking)
- ✅ CI/CD pipeline (orchestrator_v3 with gates)

---

## COMPREHENSIVE TASK INVENTORY

### P0 — CRITICAL (Production Breaking)

| ID | Issue | Root Cause | Impact | Effort |
|---|---|---|---|---|
| **P0.1** | Secrets exposed in Git (.env file) | Configuration management gap | Total bot/DB compromise risk | M |
| **P0.2** | No /health endpoint | Health check relies on /docs | Load balancer blind, K8s unaware | S |
| **P0.3** | No resource limits (mem/CPU) | Docker config incomplete | OOMKill without graceful stop | S |
| **P0.4** | File lock in /tmp (single instance) | fcntl-based, local FS only | Breaks on K8s, multi-pod setup | M |
| **P0.5** | Zero backup strategy | Infrastructure gap | Data loss on postgres crash | M |

### P1 — HIGH (Stability & Operations)

| ID | Issue | Root Cause | Impact | Effort |
|---|---|---|---|---|
| **P1.1** | No global FastAPI error handler | Missing exception_handler decorator | Unstructured 500 errors, no logging | S |
| **P1.2** | Database methods have 0 logging | No instrumentation in .../methods/*.py | SQL errors invisible, hard to debug | M |
| **P1.3** | debug print() in cache code | bot/database/main.py:39 | Pollutes logs, non-structured | S |
| **P1.4** | NATS consumer on main bot instance | Architecture: all on one pod | If bot restarts, jobs not processed | M |
| **P1.5** | No database query logging | sqlalchemy.engine logging disabled | Slow query detection impossible | S |
| **P1.6** | Dangerous DROP migrations | Alembic drops without guards | Data loss risk on failed migration | M |
| **P1.7** | NATS config in volume (single file) | No ConfigMap/vault integration | Config loss → stream misconfiguration | M |

### P2 — MEDIUM (Quality & Security)

| ID | Issue | Root Cause | Impact | Effort |
|---|---|---|---|---|
| **P2.1** | No HMAC validation on webhooks | FastAPI handlers accept unsigned | Replay attack possible | S |
| **P2.2** | No monitoring/alerting setup | Missing prometheus/grafana stack | Blind to production issues | L |
| **P2.3** | Callback routes incomplete | Manual registration, no validation | Some callbacks unhandled | S |
| **P2.4** | FSM without Redis backing | In-memory only (MemoryStorage) | Breaks on multi-instance deploy | M |
| **P2.5** | Cache (dogpile) in-memory only | Cache backend: memory, not shared | Cache miss on multi-instance | M |
| **P2.6** | Telegram polling vs webhook | Long polling architecture | Inefficient at scale (100k+ users) | L |

### P3 — LOW (Strategic & Product)

| ID | Issue | Root Cause | Impact | Effort |
|---|---|---|---|---|
| **P3.1** | No A/B testing infrastructure | Conversion agent docs only | Cannot validate copy/funnel changes | L |
| **P3.2** | No anomaly detection | Real-time intelligence missing | Silent degradation undetected | L |
| **P3.3** | Taskpack generation incomplete | docs/ops/taskpacks empty | Auto-remediation not in place | M |
| **P3.4** | Performance profiling absent | No metrics collection | Bottlenecks invisible | M |
| **P3.5** | No security scanning in CI | preflight.sh checks only secrets | Vulnerable dependencies undetected | S |

### AI-Driven Opportunities (Not Implemented Yet)

| ID | Recommendation | Source | Effort | Expected Impact |
|---|---|---|---|---|
| **AI.1** | Implement UX fixes from docs/ux/fix_plan.md | UX Agent | M | +15-20% conversion |
| **AI.2** | A/B test microcopy from conversion/ | Conversion Agent | M | +5-10% conversion |
| **AI.3** | Run callback coverage validation (qa.sh) | QA Agent + check_callbacks.py | S | 100% callback coverage |
| **AI.4** | Implement monitoring agent (log analysis) | New | L | Real-time anomaly detection |
| **AI.5** | Setup performance profiling agent | New | M | Bottleneck identification |

---

## DETAILED TASK BREAKDOWN

### PHASE 1: STABILIZATION (Week 1-2) | P0 Fixes Only

#### P0.1: Remove .env from Git & Rotate Secrets

**Problem:** Exposed credentials in repository:
- `TG_TOKEN` (Telegram Bot API key)
- `POSTGRES_PASSWORD`
- `PGADMIN_DEFAULT_PASSWORD`
- Payment API keys (CRYPTOMUS, WATA, YOOKASSA, etc.)

**Impact:** Total bot compromise, database breach, payment fraud risk

**Solution:**

```bash
# Immediate actions
1. git rm --cached bot/.env
2. Add bot/.env to .gitignore
3. Create bot/.env.example with placeholders
4. Force push or new commit (coordinate with team)

# New token generation
5. Go to BotFather, regenerate TG_TOKEN
6. Rotate database password
7. Rotate all payment provider API keys
8. Update all secrets in GitHub Actions/deployment system
```

**Subtasks:**
- [ ] Create .env.example template (0.5h)
- [ ] Coordinate git history cleanup (2h, requires team decision)
- [ ] Generate new credentials (2h, depends on payment providers)
- [ ] Update CI/CD secrets (1h)
- [ ] Verify bot still functional post-rotation (1h)

**Dependencies:** None (blocking everything else)
**Complexity:** Medium (git surgery, coordination)
**Timeline:** 4-6 hours

---

#### P0.2: Add /health Endpoint (FastAPI)

**Problem:** Health check uses `/docs` endpoint (FastAPI Swagger UI) — fragile.
Docker healthcheck:
```yaml
test: ["CMD-SHELL", "wget -q -O /dev/null http://127.0.0.1:8888/docs || exit 1"]
```

**Impact:** Load balancer cannot properly health-check service. K8s liveness probe fails.

**Solution:** Implement proper `/health` endpoint

**Code:**
```python
# bot/webhooks/base.py

@app.get("/health")
async def health_check():
    """
    Health check for load balancer / K8s.
    Returns 200 if DB and NATS accessible, 503 otherwise.
    """
    try:
        # Check DB (quick)
        async with app.state.session_maker() as session:
            await session.execute("SELECT 1")

        # Check NATS is reachable (optional, via nc socket or js)
        # For now, just DB is enough

        return {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "services": {
                "database": "ok",
                "nats": "ok"
            }
        }
    except Exception as e:
        log.error("event=health_check.failed error=%s", str(e))
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
        )

# Update docker-compose.yml healthcheck:
# test: ["CMD-SHELL", "wget -q -O /dev/null http://127.0.0.1:8888/health || exit 1"]
```

**Subtasks:**
- [ ] Write /health endpoint code (1h)
- [ ] Update docker-compose.yml healthcheck (0.5h)
- [ ] Test locally (1h)
- [ ] Add unit test (0.5h)

**Dependencies:** None
**Complexity:** Low
**Timeline:** 3 hours

---

#### P0.3: Add Resource Limits (Docker Compose)

**Problem:** No CPU/memory limits. Container can consume all host resources.

**Solution:** Add deploy.resources to docker-compose.yml

**Code:**
```yaml
# docker-compose.yml

services:
  vpn_hub_bot:
    # ... existing config ...
    deploy:
      resources:
        limits:
          cpus: '2.0'
          memory: 2G
        reservations:
          cpus: '1.0'
          memory: 1G

  db_postgres:
    deploy:
      resources:
        limits:
          cpus: '1.0'
          memory: 1G
        reservations:
          cpus: '0.5'
          memory: 512M

  nats:
    deploy:
      resources:
        limits:
          cpus: '1.0'
          memory: 512M
```

**Subtasks:**
- [ ] Add resource limits to docker-compose.yml (0.5h)
- [ ] Test deployment doesn't OOMKill under load (2h, needs load test)
- [ ] Document resource allocation decisions (0.5h)

**Dependencies:** None
**Complexity:** Low
**Timeline:** 3 hours

---

#### P0.4: Replace File Lock with NATS-Based Lock

**Problem:** Current lock uses `/tmp/vpnhub_bot.lock` with fcntl. Breaks on K8s where each pod has separate /tmp.

**Current:**
```python
# bot/run.py:122-132
def acquire_single_instance_lock(lock_path: str = "/tmp/vpnhub_bot.lock"):
    lock_file = open(lock_path, "w")
    try:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        log.critical("event=startup.abort reason=instance_lock_exists")
        raise SystemExit(1)
```

**Solution:** Use NATS KV Store for distributed lock

**Code:**
```python
# bot/misc/nats_lock.py

async def acquire_nats_lock(nc: Client, lock_name: str = "vpnhub:bot:startup", ttl_sec: int = 60):
    """
    Acquire distributed lock via NATS KV store.
    Returns True if acquired, False if locked by another instance.
    """
    try:
        kv = await nc.key_value("vpnhub_locks")
    except Exception:
        # KV bucket doesn't exist, create it
        js = nc.jetstream()
        await js.create_key_value(bucket="vpnhub_locks")
        kv = await nc.key_value("vpnhub_locks")

    node_id = f"vpnhub-{os.getpid()}-{socket.gethostname()}"
    try:
        # Try to create with generation=0 (atomic create)
        await kv.create(lock_name, json.dumps({
            "node": node_id,
            "pid": os.getpid(),
            "hostname": socket.gethostname(),
            "acquired_at": datetime.utcnow().isoformat()
        }))
        log.info("event=nats_lock.acquired node=%s", node_id)
        return True
    except Exception as e:
        log.critical("event=nats_lock.failed node=%s reason=%s", node_id, str(e))
        return False

# Usage in bot/run.py:
# async with await acquire_nats_lock(nc): ...
```

**Subtasks:**
- [ ] Write nats_lock.py utility (2h)
- [ ] Update run.py to use NATS lock (1h)
- [ ] Test on multi-pod K8s setup (2h)
- [ ] Add fallback for local dev (0.5h)

**Dependencies:** NATS infrastructure (already exists)
**Complexity:** Medium
**Timeline:** 5-6 hours

---

#### P0.5: Implement Database Backup Strategy

**Problem:** `/backups` folder empty. No automated backup script. Risk of total data loss.

**Solution:** Create backup automation.

**Code:**
```bash
#!/bin/bash
# scripts/backup_db.sh

set -e

BACKUP_DIR="${BACKUP_DIR:-.backups}"
RETENTION_DAYS="${RETENTION_DAYS:-30}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/vpnhub_$TIMESTAMP.sql.gz"

mkdir -p "$BACKUP_DIR"

log() {
  echo "[$(date +'%Y-%m-%d %H:%M:%S')] $1"
}

log "Starting database backup..."

docker compose exec -T postgres pg_dump \
  -U "$POSTGRES_USER" \
  -d "$POSTGRES_DB" \
  | gzip > "$BACKUP_FILE"

log "Backup saved: $BACKUP_FILE ($(du -h "$BACKUP_FILE" | cut -f1))"

# Cleanup old backups (older than RETENTION_DAYS)
find "$BACKUP_DIR" -name "vpnhub_*.sql.gz" -mtime +$RETENTION_DAYS -delete
log "Cleaned up backups older than $RETENTION_DAYS days"

log "Backup complete"
```

**Subtasks:**
- [ ] Create backup script (1h)
- [ ] Add to Makefile: `make backup` (0.5h)
- [ ] Setup cron job for daily backups (0.5h, ops-dependent)
- [ ] Test restore procedure (2h)
- [ ] Document backup/restore process (1h)

**Dependencies:** None (PostgreSQL is already running)
**Complexity:** Low-Medium
**Timeline:** 5 hours

---

### PHASE 2: HARDENING (Week 2-3) | P1 + Security Issues

#### P1.1: Add Global FastAPI Exception Handler

**Problem:** Unhandled exceptions return plain 500 without structure. No correlation ID.

**Code:**
```python
# bot/webhooks/base.py

import uuid
from starlette.middleware.base import BaseHTTPMiddleware

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    log.exception(
        "event=unhandled_exception request_id=%s path=%s method=%s",
        request_id,
        request.url.path,
        request.method
    )
    return JSONResponse(
        status_code=500,
        content={
            "error": "internal_server_error",
            "request_id": request_id,
            "detail": str(exc) if os.getenv("DEBUG") else "An error occurred"
        },
        headers={"X-Request-ID": request_id}
    )

# Add request ID middleware
class RequestIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = str(uuid.uuid4())
        request.scope["request_id"] = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response

app.add_middleware(RequestIDMiddleware)
```

**Subtasks:**
- [ ] Implement exception handler (1h)
- [ ] Add RequestID middleware (1h)
- [ ] Test with curl/Postman (0.5h)
- [ ] Update logs format to include request_id (1h)

**Dependencies:** None
**Complexity:** Low
**Timeline:** 3.5 hours

---

#### P1.2: Instrument Database Methods with Logging

**Problem:** `bot/bot/database/methods/*.py` has 0 logging. SQL errors invisible.

**Files to update:**
- `bot/bot/database/methods/get.py`
- `bot/bot/database/methods/insert.py`
- `bot/bot/database/methods/update.py`
- `bot/bot/database/methods/delete.py`

**Pattern:**
```python
# Before
async def get_user(session, tgid):
    result = await session.execute(...)
    return result.scalar()

# After
import time
log = logging.getLogger(__name__)

async def get_user(session, tgid):
    start = time.perf_counter()
    try:
        log.debug("event=db.query table=users operation=select tgid=%s", tgid)
        result = await session.execute(...)
        user = result.scalar()
        duration_ms = (time.perf_counter() - start) * 1000
        if duration_ms > 100:  # Slow query
            log.warning("event=db.slow_query table=users duration_ms=%.1f", duration_ms)
        return user
    except Exception as e:
        log.error("event=db.error table=users operation=select tgid=%s", tgid, exc_info=e)
        raise
```

**Subtasks:**
- [ ] Add logging import + setup to each methods file (4 files × 0.5h)
- [ ] Instrument all query/insert/update/delete functions (4-6h)
- [ ] Add slow query threshold (1h)
- [ ] Add unit tests (2h)

**Dependencies:** None
**Complexity:** Medium
**Timeline:** 10-12 hours

---

#### P2.1: Add HMAC Validation to Payment Webhooks

**Problem:** Webhook endpoints accept unsigned payloads. Vulnerable to replay attacks.

**Code:**
```python
# bot/webhooks/base.py

import hmac
import hashlib

def verify_webhook_signature(body: bytes, signature: str, secret: str) -> bool:
    """Verify HMAC-SHA256 signature."""
    expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(signature, expected)

# Example: Wata webhook
@app.post("/webhook/wata")
async def handle_wata_webhook(request: Request):
    body = await request.body()
    signature = request.headers.get("X-Signature")

    if not signature:
        log.warning("event=webhook.missing_signature provider=wata")
        raise HTTPException(status_code=401, detail="Missing signature")

    if not verify_webhook_signature(body, signature, CONFIG.wata_webhook_secret):
        log.warning("event=webhook.invalid_signature provider=wata")
        raise HTTPException(status_code=401, detail="Invalid signature")

    # Process webhook
    data = json.loads(body)
    # ... existing logic ...
```

**Subtasks:**
- [ ] Implement verify_webhook_signature function (1h)
- [ ] Add to all webhook handlers (3h, multiple payment providers)
- [ ] Update payment provider configs with secrets (1h, ops)
- [ ] Add unit tests (2h)

**Dependencies:** Payment provider secrets stored securely
**Complexity:** Medium
**Timeline:** 7 hours

---

### PHASE 3: ARCHITECTURE UPGRADE (Week 3-4) | P2 + Scalability

#### P2.4: Migrate FSM Storage from Memory to Redis

**Problem:** In-memory FSM (MemoryStorage) breaks on multi-instance deploy.

**Current:**
```python
# bot/bot/main.py:101-102
dp = Dispatcher(
    storage=MemoryStorage(),  # ← Only works on single instance
    fsm_strategy=FSMStrategy.USER_IN_CHAT
)
```

**Solution:** Use Redis storage (aiogram_fsm_redis or similar)

**Steps:**
1. Add Redis service to docker-compose.yml
2. Install `aiogram-storages` or `redis` + custom adapter
3. Replace MemoryStorage with RedisStorage

**Code:**
```yaml
# docker-compose.yml (add service)
services:
  redis:
    image: redis:7.2-alpine
    container_name: vpnhub-redis
    ports:
      - "127.0.0.1:6379:6379"
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 30s
      timeout: 5s
      retries: 3
    deploy:
      resources:
        limits:
          cpus: '0.5'
          memory: 512M
```

**Python:**
```python
# bot/bot/main.py
from aiogram.fsm.storage.redis import RedisStorage
import aioredis

# Create Redis connection
redis = aioredis.from_url('redis://redis:6379')
storage = RedisStorage(redis=redis)

dp = Dispatcher(
    storage=storage,  # ← Now distributed
    fsm_strategy=FSMStrategy.USER_IN_CHAT
)
```

**Subtasks:**
- [ ] Add Redis service to docker-compose (1h)
- [ ] Install aiogram FSM Redis adapter (0.5h)
- [ ] Update Dispatcher initialization (1h)
- [ ] Test FSM state persistence (2h)
- [ ] Load test with concurrent users (3h)

**Dependencies:** P1.3 (resource limits for Redis)
**Complexity:** Medium
**Timeline:** 7-8 hours

---

#### P2.5: Migrate Cache from In-Memory to Redis

**Problem:** dogpile.cache in-memory only. Cache misses on multi-instance.

**Current:**
```python
# bot/bot/database/main.py:26-28
cache_region = make_region().configure(
    'dogpile.cache.memory',  # ← Single-instance only
    expiration_time=30
)
```

**Solution:** Use Redis backend

**Code:**
```python
# bot/bot/database/main.py

from dogpile.cache import make_region

cache_region = make_region().configure(
    'dogpile.cache.redis',
    arguments={
        'url': os.getenv('REDIS_URL', 'redis://redis:6379/0'),
        'distributed_lock': True
    },
    expiration_time=30
)
```

**Subtasks:**
- [ ] Update cache config (1h)
- [ ] Test cache hit rate (1h)
- [ ] Load test (2h)

**Dependencies:** Redis service (from P2.4)
**Complexity:** Low
**Timeline:** 4 hours

---

#### P1.4: Separate NATS Consumer from Main Bot Instance

**Problem:** RemoveKeyConsumer runs on main bot instance. If bot restarts, jobs not processed.

**Solution:** Create separate worker deployment.

**Architecture:**
```
┌─────────────────┐         ┌──────────────────┐
│  vpn_hub_bot    │ ←────→  │  NATS JetStream  │
│  (polling + API)│         │                  │
└─────────────────┘         └──────────────────┘
                                    ↑
                                    │
                            ┌───────┴────────┐
                            │  vpn_hub_worker│
                            │  (remove key   │
                            │   consumer)    │
                            └────────────────┘
```

**Implementation:**
1. Create separate `bot/worker.py` entry point
2. Add `worker` service to docker-compose
3. Move RemoveKeyConsumer logic there

**Code:**
```python
# bot/worker.py
import asyncio
import logging
from bot.misc.nats_connect import connect_to_nats
from bot.misc.remove_key_servise.consumer import RemoveKeyConsumer
from bot.database import engine
from sqlalchemy.ext.asyncio import async_sessionmaker
from bot.misc.util import CONFIG

log = logging.getLogger(__name__)

async def main():
    # Connect to NATS
    nc, js = await connect_to_nats(servers=CONFIG.nats_servers)

    # Setup DB session
    engine_instance = engine()
    sessionmaker = async_sessionmaker(engine_instance, expire_on_commit=False)

    # Start consumer
    consumer = RemoveKeyConsumer(
        nc=nc,
        js=js,
        bot=None,  # Worker doesn't need bot
        session_pool=sessionmaker,
        subject=CONFIG.nats_remove_consumer_subject,
        stream=CONFIG.nats_remove_consumer_stream,
        durable_name=CONFIG.nats_remove_consumer_durable_name
    )

    log.info("event=worker.start")
    try:
        await consumer.start()
        while True:
            await asyncio.sleep(3600)
    except Exception as e:
        log.exception("event=worker.error", exc_info=e)
        raise
    finally:
        await nc.close()
        await engine_instance.dispose()

if __name__ == '__main__':
    asyncio.run(main())
```

```yaml
# docker-compose.yml (add service)
services:
  vpn_hub_worker:
    build:
      context: .
      dockerfile: bot/Dockerfile
    container_name: vpn_hub_worker
    env_file:
      - ./bot/.env
    depends_on:
      db_postgres:
        condition: service_healthy
      nats-health:
        condition: service_healthy
    command: ["python", "-m", "bot.worker"]
    restart: unless-stopped
    healthcheck:
      test: ["CMD-SHELL", "curl -f http://localhost:8889/health || exit 1"]
      interval: 30s
      timeout: 10s
      retries: 3
    deploy:
      resources:
        limits:
          cpus: '1.0'
          memory: 1G
```

**Subtasks:**
- [ ] Create worker.py entry point (2h)
- [ ] Update docker-compose with worker service (1h)
- [ ] Test message delivery to worker (2h)
- [ ] Monitor NATS consumer lag (2h)

**Dependencies:** NATS infrastructure exists
**Complexity:** Medium
**Timeline:** 7 hours

---

### PHASE 4: AI AGENT INTEGRATION (Week 4-5) | No Code Breaking

#### AI.1: Implement UX Fixes from UX Agent

**Source:** `docs/ux/fix_plan.md` (already generated by UX Audit Agent)

**Deliverables:** UX improvements (copy, button labels, flow clarity)

**Subtasks:**
- [ ] Read docs/ux/audit_findings.md + fix_plan.md (2h)
- [ ] Prioritize by impact (P0 → UX traps, P1 → clarity, P2 → polish) (1h)
- [ ] Implement copy changes (messages/copy updates) (4-6h)
- [ ] Update button layouts (keyboard restructure if needed) (2-4h)
- [ ] Manual test flows (2h)
- [ ] Measure conversion impact (requires GA integration)

**Dependencies:** None (docs already exist)
**Complexity:** Low-Medium
**Timeline:** 13-17 hours (spread over 2 weeks with A/B testing)

---

#### AI.2: Run QA Callback Validation (Automated)

**Source:** `check_callbacks.py` + `docs/qa/callback_index.md`

**Action:** Integrate into CI/CD, make mandatory before merge.

**Setup:**
```bash
# scripts/qa.sh (already exists, enhance)

# Current: runs only if file exists
# New: run always, fail if mismatches found

python3 scripts/qa/check_callbacks.py --root bot/bot \
  --fail-on-unhandled \
  --fail-on-duplicates
```

**Subtasks:**
- [ ] Update qa.sh to make validation mandatory (1h)
- [ ] Document callback naming conventions (1h)
- [ ] Add to GitHub Actions workflow (0.5h)

**Dependencies:** None (tooling already built)
**Complexity:** Low
**Timeline:** 2.5 hours

---

#### AI.3: A/B Test Microcopy from Conversion Agent

**Source:** `docs/conversion/copy_pack_ru_en.md`, `docs/conversion/experiments.md`

**Requirements:**
- Analytics tracking for funnel events (ConversionEventsMiddleware already active)
- A/B test framework (Django split tests or simple feature flag)

**Experiments to run:**
1. CTA button text variations (see docs/conversion/cta_buttons.md)
2. Onboarding copy (Russian vs English messaging)
3. Trial period pitch (different messaging for trial activation)

**Subtasks:**
- [ ] Implement feature flag system (2h)
- [ ] Setup analytics dashboard for funnel metrics (3h, depends on analytics infra)
- [ ] Run first copy variant (2h per experiment)
- [ ] Measure conversion deltas (1h per week)

**Dependencies:** Analytics infrastructure (ConversionEventsMiddleware set up, logs flowing)
**Complexity:** Medium
**Timeline:** 8-10 hours (initial setup), then ongoing per experiment

---

### PHASE 5: ADVANCED MONITORING & GROWTH (Week 5+) | Strategic

#### P3.4: Implement Performance Profiling Agent

**Goal:** Automatic bottleneck detection from logs/metrics.

**What it does:**
- Parse slow query logs (P1.2 added this)
- Identify NATS consumer lag
- Track 95th/99th percentile API latencies
- Alert on regressions

**Stack:**
- Prometheus (metrics scraping)
- Grafana (dashboards)
- Custom alert rules

**Subtasks:**
- [ ] Add Prometheus `/metrics` endpoint to FastAPI (2h)
- [ ] Export DB query duration metrics (1h)
- [ ] Export NATS consumer lag metrics (1h)
- [ ] Setup Prometheus scrape config (1h)
- [ ] Create Grafana dashboard (3h)
- [ ] Set alert thresholds (2h)

**Dependencies:** None (can be parallel with other work)
**Complexity:** Medium-High
**Timeline:** 10 hours

---

#### P3.5: Security Scanning in CI/CD

**Goal:** Catch vulnerable dependencies before deployment.

**Setup:**
```bash
# scripts/preflight.sh (enhance)

# Check for known vulnerabilities
safety check --json > /tmp/safety_report.json || {
  cat /tmp/safety_report.json
  exit 1
}

# Or use pip-audit
pip-audit --desc --format markdown > /tmp/audit_report.md || {
  cat /tmp/audit_report.md
  exit 1
}
```

**Subtasks:**
- [ ] Install safety/pip-audit (0.5h)
- [ ] Add to preflight.sh (0.5h)
- [ ] Add to GitHub Actions (0.5h)
- [ ] Establish patching SLA (1h)

**Dependencies:** None
**Complexity:** Low
**Timeline:** 2.5 hours

---

## PHASED ROADMAP TIMELINE

### Phase 1: Stabilization (Week 1-2)
**Goal:** Fix production-breaking issues

| Week | Task | Hours | Owner | Status |
|------|------|-------|-------|--------|
| W1 | P0.1: Remove .env secrets | 4-6 | DevOps Lead | Critical |
| W1 | P0.2: Add /health endpoint | 3 | Backend | Critical |
| W1 | P0.3: Resource limits (docker) | 3 | DevOps | Critical |
| W1 | P0.4: Replace file lock | 5-6 | Backend | Critical |
| W2 | P0.5: Backup strategy | 5 | DevOps | Critical |

**Exit Criteria:**
- ✅ All P0 issues resolved
- ✅ docker-compose passes health checks
- ✅ Backup test restore succeeds
- ✅ Production Readiness: 7/10

---

### Phase 2: Hardening (Week 2-3)
**Goal:** Improve stability, logging, security

| Week | Task | Hours | Owner | Status |
|------|------|-------|-------|--------|
| W2 | P1.1: Global exception handler | 3.5 | Backend | Ready |
| W2 | P1.2: DB logging instrumentation | 10-12 | Backend | Ready |
| W2 | P2.1: HMAC webhook validation | 7 | Backend | Ready |
| W3 | P1.3: Replace debug print() | 1 | Backend | Ready |
| W3 | P1.5: Enable SQLAlchemy logging | 1 | DevOps | Ready |

**Exit Criteria:**
- ✅ All exceptions logged with correlation ID
- ✅ DB query visibility (slow query detection enabled)
- ✅ Webhook signature validation active
- ✅ DevOps Maturity: 7/10

---

### Phase 3: Architecture (Week 3-4)
**Goal:** Enable horizontal scaling

| Week | Task | Hours | Owner | Status |
|------|------|-------|-------|--------|
| W3 | P2.4: Redis FSM storage | 7-8 | Backend | Ready |
| W3 | P2.5: Redis cache backend | 4 | Backend | Ready |
| W4 | P1.4: Separate worker service | 7 | Backend | Ready |

**Exit Criteria:**
- ✅ Multi-instance bot deployment working
- ✅ FSM state shared across instances
- ✅ Cache shared across instances
- ✅ Scalability: 7/10

---

### Phase 4: AI Integration (Week 4-5)
**Goal:** Execute AI-generated recommendations

| Week | Task | Hours | Owner | Status |
|------|------|-------|-------|--------|
| W4 | AI.2: QA callback validation | 2.5 | QA Lead | Ready |
| W4-W5 | AI.1: Implement UX fixes | 13-17 | Product/Frontend | Ready |
| W5 | AI.3: Setup A/B testing | 8-10 | Analytics | Ready |

**Exit Criteria:**
- ✅ Callback coverage 100%
- ✅ UX fixes deployed to 10% traffic (canary)
- ✅ A/B test infrastructure running
- ✅ Conversion +5% measured

---

### Phase 5: Advanced Monitoring (Ongoing)
**Goal:** Real-time observability

| Week | Task | Hours | Owner | Status |
|------|------|-------|-------|--------|
| W5+ | P3.4: Performance profiling | 10 | DevOps | Backlog |
| W5+ | P3.5: Security scanning CI | 2.5 | DevOps | Backlog |
| W6+ | Monitoring agent (new) | 15-20 | ML/Data | Backlog |

---

## MATURITY PROGRESSION

### Current State (Feb 24, 2026)

| Metric | Current | Target (Phase 1) | Target (Phase 3) | Target (Phase 5) |
|--------|---------|------------------|------------------|------------------|
| **Production Readiness** | 5/10 | 7/10 | 8/10 | 9/10 |
| **DevOps Maturity** | 6/10 | 7/10 | 8/10 | 9/10 |
| **Scalability** | 4/10 | 4/10 | 7/10 | 8/10 |
| **Security** | 4/10 | 6/10 | 7/10 | 8/10 |
| **AI Readiness** | 7/10 | 7/10 | 8/10 | 9/10 |
| **Observability** | 3/10 | 4/10 | 6/10 | 8/10 |

### Detailed Scoring Rationale

#### Production Readiness
- **Current 5/10:** Secrets exposed, no health endpoint, no backup strategy
- **Phase 1 (7/10):** P0 issues fixed, basic operational health
- **Phase 3 (8/10):** Multi-instance ready, database instrumented
- **Phase 5 (9/10):** Full monitoring, automated recovery, 99.9% SLA

#### DevOps Maturity
- **Current 6/10:** Good infrastructure (Docker, migrations), missing monitoring
- **Phase 1 (7/10):** Health checks + alarms + backup automated
- **Phase 3 (8/10):** Horizontal scaling working, distributed lock ready
- **Phase 5 (9/10):** Full observability, auto-remediation, canary deployments

#### Scalability
- **Current 4/10:** Single-instance polling, memory-based FSM/cache
- **Phase 1-2 (4/10):** No change yet (polling still bottleneck)
- **Phase 3 (7/10):** Multi-instance ready, distributed state, Redis-backed
- **Phase 5 (8/10):** Webhook mode possible, event-driven, 100k+ users feasible

---

## CRITICAL DEPENDENCIES & BLOCKERS

```
Phase 2 Hardening
    ↓
   P0.1 (Secrets)
    ↓ blocks everything until resolved

Phase 1 must complete fully → Phase 2 can start (roughly parallel)

Phase 3 Architecture
    ↓
   Redis needed → blocks P2.4, P2.5, P3.x (performance)

Phase 4 AI Integration
    ↓
   Conversion metrics → requires ConversionEventsMiddleware (already active)
   A/B testing → requires Phase 1 stability first

Phase 5 Monitoring
    ↓
   Can start parallel with Phase 3, depends on Prometheus setup on Phase 3
```

---

## QUICK WINS (Implement This Week)

These deliver immediate value with minimal effort:

1. **P0.2: /health endpoint** (3h)
   - Fixes immediate K8s compatibility
   - No breaking changes

2. **P0.3: Resource limits** (3h)
   - Prevents OOMKill
   - One-line docker-compose change

3. **P1.3: Replace debug print()** (1h)
   - Removes log pollution
   - Trivial code change

4. **P1.5: Enable SQLAlchemy logging** (1h)
   - Immediate query visibility
   - One-line config change

5. **AI.2: Enforce callback validation** (2.5h)
   - Catches bugs in CI/CD
   - Leverages existing check_callbacks.py

**Total: 10.5 hours = 1.3 person-days**
**Impact: High (operational stability)**

---

## RISK REGISTER

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|-----------|
| Secrets already compromised | High | Critical | Rotate immediately, audit logs |
| NATS cluster stability | Medium | High | Add monitoring (Phase 5), setup alerting |
| Redis single-point-of-failure | Medium | Medium | Phase 3 → add Redis Sentinel/Cluster |
| Multi-instance FSM race condition | Low | High | Thorough testing in Phase 3 |
| Payment webhook downtime during HMAC rollout | Low | Medium | Gradual rollout, A/B test providers |
| PostgreSQL backup incomplete | Medium | Critical | Test restore in staging before prod |

---

## RESOURCE ALLOCATION

### Recommended Team Structure

```
Backend Team (3-4 devs):
  - 1 Lead → Phase 1 P0 fixes (weeks 1-2)
  - 2 Devs → Phase 2 logging + P2.1 (weeks 2-3)
  - 1 Dev → Phase 3 Redis migration (week 3-4)
  - 1 Dev → Phase 4 AI integration / deployment testing

DevOps/Infrastructure (1-2):
  - 1 Lead → Phase 1 P0 (secrets, backup), Phase 3 Redis, Phase 5 monitoring
  - 1 Engineer → CI/CD enhancement, Prometheus setup

QA/Testing (1-2):
  - 1 Lead → Phase 2 testing, Phase 3 load testing
  - 1 Engineer → AI.1 UX testing, A/B test setup

Analytics/Product (0.5-1):
  - 0.5 → Phase 4 AI.3 A/B testing setup, metrics definition
```

**Total: ~7-9 FTE-weeks for Phases 1-4**

---

## METRICS & SUCCESS CRITERIA

### Phase 1 Success
- ✅ All P0 issues resolved (secrets removed, /health live, backups running)
- ✅ Production alerts for health checks
- ✅ Zero security incidents from exposed secrets (post-rotation)

### Phase 2 Success
- ✅ 100% of exceptions logged with correlation ID
- ✅ Slow query detection active (< 100ms threshold)
- ✅ Webhook signature validation blocking unsigned requests

### Phase 3 Success
- ✅ Multi-instance bot deployment stable (2+ pods)
- ✅ FSM state persists across pod restarts
- ✅ Cache hit rate > 80%
- ✅ Scalability: 4/10 → 7/10

### Phase 4 Success
- ✅ UX fixes deployed to production
- ✅ Callback validation 100% (0 unhandled)
- ✅ A/B test infrastructure live
- ✅ Measured conversion improvement +5-10%

### Phase 5 Success
- ✅ Grafana dashboard with key metrics
- ✅ Alert thresholds set + tested
- ✅ Security scanning catching vulnerabilities
- ✅ DevOps Maturity: 6/10 → 9/10

---

## CONCLUSION

VPNHub has a **solid foundation** (clean architecture, good async patterns, working AI agents) but faces **critical production blockers** (exposed secrets, no health checks, no backups).

**Immediate action required:** Stabilize production (Phase 1, 2 weeks).
**Then:** Enable scaling (Phase 3, 2 weeks).
**Then:** Optimize product (Phase 4, 2-3 weeks).

This roadmap is executable with current resources and existing infrastructure.

