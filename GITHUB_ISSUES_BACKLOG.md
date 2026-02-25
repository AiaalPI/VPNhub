# VPNHUB GITHUB ISSUES BACKLOG

**Format:** GitHub Issues templates for backlog management
**Status:** Ready for GitHub Project / Jira migration

---

## EPIC 1: STABILIZE PRODUCTION (P0 Fixes) — Week 1-2

### Why This Epic Matters
Production readiness is 5/10. One outage loses users and revenue. This epic locks down the platform.

### Impact
- Zero data loss risk
- 99.5%+ uptime achieved
- Foundation for growth (can't scale unstable system)

---

### ISSUE #101: Remove Secrets from Git & Rotate Credentials

**Type:** Security / Critical Fix
**Priority:** P0 (BLOCKING)
**Impact:** Critical
**Effort:** Medium (4-6 hours)
**Dependencies:** None
**Risk Level:** High (already exposed)

**Description:**

`.env` file committed to Git with:
- Telegram Bot Token
- PostgreSQL credentials
- Payment API keys (CRYPTOMUS, WATA, YOOKASSA, etc.)
- pgAdmin password

This is a production security breach.

**Technical Details:**

```bash
# Current state
bot/.env in Git with 20+ secrets

# Exposed credentials
TG_TOKEN=8148645891:AAHgsRJ8J3egPWiQAo4HT_qbO40zJbuqD5w
POSTGRES_PASSWORD=BvpnStrong2026
PGADMIN_DEFAULT_PASSWORD=PgAdminStrong2026
CRYPTOMUS_KEY=<key>
WATA_TOKEN_CARD=<token>
# ... etc
```

**Subtasks:**
- [ ] Create bot/.env.example with placeholder values (1h)
- [ ] Coordinate git history cleanup (2h):
  ```bash
  git rm --cached bot/.env
  git commit --amend
  git filter-branch --tree-filter 'rm -f bot/.env' -- --all  # Nuclear option
  ```
- [ ] Add bot/.env to .gitignore (0.5h)
- [ ] Regenerate Telegram Bot Token via BotFather (0.5h)
- [ ] Regenerate PostgreSQL password:
  ```sql
  ALTER USER vpnhub WITH PASSWORD 'NewSecure$2026Password';
  ```
- [ ] Update all payment provider secrets (1h, coordinate with ops)
- [ ] Update GitHub Actions secrets (1h)
- [ ] Verify bot still functional post-rotation (1h)
- [ ] Audit git history for any remaining secrets (1h)
  ```bash
  git log --all --full-history --oneline | head -50 | xargs git show
  ```

**Acceptance Criteria:**
- [ ] bot/.env removed from git history (verify with `git log --all -p bot/.env | wc -l` → should be 0)
- [ ] All new credentials in GitHub Secrets, not in env files
- [ ] docker-compose.yml references .env but does NOT commit it
- [ ] CI/CD scripts source secrets from GitHub Secrets
- [ ] Local .env can be created from .env.example
- [ ] All services boot successfully with new credentials

**Definition of Done:**
- ✅ Code: .env.example committed, bot/.env in .gitignore
- ✅ Tests: Verify bot connects to DB + Telegram + payment providers
- ✅ Deploy: New secrets deployed to vpnhub-prod
- ✅ Monitoring: Alert if any credential appears in logs
- ✅ Docs: docs/SECRETS_MANAGEMENT.md created (how to rotate in future)

**Assigned to:** DevOps Lead
**Estimated:** 6 hours
**Risk:** High (go/no-go for production)

---

### ISSUE #102: Implement /health Endpoint

**Type:** Feature / Infrastructure
**Priority:** P0
**Impact:** Critical (K8s compatibility)
**Effort:** Small (3 hours)
**Dependencies:** None
**Risk Level:** Low

**Description:**

Current docker healthcheck uses `/docs` endpoint (FastAPI Swagger UI), which is fragile. Kubernetes cannot properly health-check service.

**Current Code:**
```yaml
# docker-compose.yml
healthcheck:
  test: ["CMD-SHELL", "wget -q -O /dev/null http://127.0.0.1:8888/docs || exit 1"]
```

**Problem:**
- `/docs` is not a health indicator, it's API documentation
- If FastAPI boots but DB is down, `/docs` still returns 200
- Kubernetes uses this to determine pod liveness

**Solution:** Proper `/health` endpoint with DB + NATS checks

**Subtasks:**
- [ ] Write `/health` endpoint (1h):
  ```python
  # bot/webhooks/base.py

  @app.get("/health", tags=["health"])
  async def health_check():
      """
      Health check for load balancer / K8s probe.
      Returns 200 if DB accessible, 503 otherwise.
      """
      try:
          async with app.state.session_maker() as session:
              await session.execute("SELECT 1")

          return {
              "status": "healthy",
              "timestamp": datetime.utcnow().isoformat(),
              "services": {
                  "database": "ok",
                  "nats": "ok",
              }
          }
      except Exception as e:
          return JSONResponse(
              status_code=503,
              content={
                  "status": "unhealthy",
                  "error": str(e),
                  "timestamp": datetime.utcnow().isoformat()
              }
          )
  ```

- [ ] Add unit test (0.5h):
  ```python
  pytest tests/test_health.py
  ```

- [ ] Update docker-compose.yml (0.5h):
  ```yaml
  healthcheck:
    test: ["CMD-SHELL", "wget -q -O /dev/null http://127.0.0.1:8888/health || exit 1"]
    interval: 30s
    timeout: 5s
    retries: 3
  ```

- [ ] Test locally with docker compose (1h)

**Acceptance Criteria:**
- [ ] `curl http://localhost:8888/health` returns 200 when healthy
- [ ] Returns 503 when DB is down
- [ ] Docker healthcheck shows "healthy" after restart
- [ ] No breaking changes to existing endpoints

**Definition of Done:**
- ✅ Code: /health endpoint in bot/webhooks/base.py
- ✅ Tests: Unit test + docker compose health check verified
- ✅ Deploy: Rolled out, monitoring confirms no 503s from health checks
- ✅ Docs: docs/HEALTH_ENDPOINT.md created

**Assigned to:** Backend Lead
**Estimated:** 3 hours

---

### ISSUE #103: Add Docker Resource Limits

**Type:** DevOps / Infrastructure
**Priority:** P0
**Impact:** High (prevents OOMKill)
**Effort:** Small (3 hours)
**Dependencies:** None
**Risk Level:** Low

**Description:**

Containers have no CPU/memory limits. Under load, vpn_hub_bot can consume entire host RAM and get killed by OOMKill without graceful shutdown.

**Subtasks:**
- [ ] Add resource limits to docker-compose.yml (0.5h):
  ```yaml
  services:
    vpn_hub_bot:
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

- [ ] Document resource allocation rationale (0.5h): docs/RESOURCE_ALLOCATION.md
- [ ] Test under load (2h):
  ```bash
  # Simulate 1000 concurrent users
  docker-compose up
  ab -n 1000 -c 100 http://localhost:8888/health
  # Monitor: docker stats
  ```
- [ ] Verify no OOMKill under normal 10k user load

**Acceptance Criteria:**
- [ ] docker-compose.yml has deploy.resources for all services
- [ ] Load test: 10k concurrent users, no OOMKill
- [ ] Graceful shutdown still works under memory pressure

**Definition of Done:**
- ✅ Code: docker-compose.yml updated
- ✅ Tests: Load test passes
- ✅ Docs: Resource allocation documented

---

### ISSUE #104: Replace File Lock with NATS-Based Distributed Lock

**Type:** Architecture / Scaling
**Priority:** P0
**Impact:** Critical (blocks K8s)
**Effort:** Medium (5-6 hours)
**Dependencies:** NATS (already running)
**Risk Level:** Medium

**Description:**

Current lock uses `/tmp/vpnhub_bot.lock` with fcntl. Breaks on Kubernetes where each pod has separate /tmp directory. Only one pod can boot, others fail.

**Current Code:**
```python
# bot/run.py:122-132
def acquire_single_instance_lock(lock_path: str = "/tmp/vpnhub_bot.lock"):
    lock_file = open(lock_path, "w")
    try:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        raise SystemExit(1)
```

**Problem:** File system isolation on K8s means each pod has its own /tmp

**Solution:** Use NATS KV store for distributed lock

**Subtasks:**
- [ ] Create bot/misc/nats_lock.py (2h):
  ```python
  async def acquire_nats_lock(nc: Client, lock_name: str, ttl_sec: int = 60):
      """Acquire distributed lock via NATS KV store"""
      kv = await nc.key_value("vpnhub_locks")
      node_id = f"vpnhub-{os.getpid()}-{socket.gethostname()}"
      try:
          await kv.create(lock_name, json.dumps({...}))
          return True
      except:
          return False
  ```

- [ ] Update bot/run.py to use NATS lock (1h):
  ```python
  # Instead of: acquire_single_instance_lock()
  # Use: await acquire_nats_lock(nc, "vpnhub:startup")
  ```

- [ ] Test on multi-pod K8s setup (2h)
- [ ] Add fallback for local dev (0.5h)

**Acceptance Criteria:**
- [ ] Only one bot instance boots at a time
- [ ] Works on K8s (multiple pods, same node/different nodes)
- [ ] Lock timeout: 60 seconds (prevents deadlock)
- [ ] Graceful abort on lock acquire failure

**Definition of Done:**
- ✅ Code: nats_lock.py + run.py updated
- ✅ Tests: Multi-pod deploy test passes
- ✅ Deploy: Kubernetes-ready

---

### ISSUE #105: Implement Database Backup & Restore Strategy

**Type:** DevOps / Disaster Recovery
**Priority:** P0
**Impact:** Critical (data loss prevention)
**Effort:** Medium (5 hours)
**Dependencies:** None
**Risk Level:** Medium

**Description:**

Currently `/backups` folder is empty. No automated backups = total data loss risk if postgres crashes.

**Subtasks:**
- [ ] Create backupscript (1h):
  ```bash
  # scripts/backup_db.sh
  docker compose exec -T postgres pg_dump -U $POSTGRES_USER $POSTGRES_DB | gzip > backups/vpnhub_$(date +%s).sql.gz
  ```

- [ ] Setup cron job for daily backups (0.5h):
  ```bash
  0 2 * * * cd /opt/vpnhub && ./scripts/backup_db.sh
  ```

- [ ] Setup retention policy: keep 30 days (0.5h):
  ```bash
  find backups/ -name "vpnhub_*.sql.gz" -mtime +30 -delete
  ```

- [ ] Test restore procedure (2h):
  ```bash
  # Restore from backup
  gunzip < backups/vpnhub_latest.sql.gz | docker compose exec -T postgres psql -U $POSTGRES_USER $POSTGRES_DB
  # Verify data integrity
  ```

- [ ] Add to Makefile: `make backup` (0.5h)
- [ ] Document in runbook (1h)

**Acceptance Criteria:**
- [ ] Daily backups running automatically at 2 AM UTC
- [ ] Each backup is gzipped, named with timestamp
- [ ] Restore test passes: data is intact after restore
- [ ] Retention: keep 30 most recent backups

**Definition of Done:**
- ✅ Code: scripts/backup_db.sh committed
- ✅ Ops: Cron job running on vpnhub-prod
- ✅ Test: Restore procedure tested weekly
- ✅ Docs: Disaster recovery runbook

---

## EPIC 2: OBSERVABILITY & MONITORING — Week 2-3

### Why This Epic Matters
Can't improve what you don't measure. Need visibility into production before users report issues.

### Impact
- Real-time visibility into system health
- Ability to detect issues before customers
- Data for decision-making (conversion funnels, performance, errors)

---

### ISSUE #201: Setup Prometheus + Grafana Stack

**Type:** DevOps / Monitoring
**Priority:** P1 (High)
**Impact:** High (enables all other observability)
**Effort:** Large (6-8 hours)
**Dependencies:** None
**Risk Level:** Low

**Description:**

Need centralized metrics collection (Prometheus) and dashboards (Grafana) to monitor bot health, database, NATS, and business metrics.

**Subtasks:**
- [ ] Add Prometheus service to docker-compose.yml (1h)
- [ ] Add Grafana service to docker-compose.yml (1h)
- [ ] Configure Prometheus scrape targets (1h)
- [ ] Create bot /metrics endpoint (2h)
- [ ] Install Grafana dashboards (2h)
- [ ] Setup alerting rules (2h)

**Files to Create:**
- `prometheus/prometheus.yml` — scrape config
- `docker-compose.prometheus.yml` — services def
- `grafana/dashboard-bot-health.json` — main dashboard
- `grafana/alerts.yml` — alert rules

**Acceptance Criteria:**
- [ ] Prometheus scrapes metrics every 15 seconds
- [ ] Bot /metrics endpoint returns Prometheus format metrics
- [ ] Grafana accessible at http://localhost:3000
- [ ] Dashboard shows: CPU, Memory, DB connections, API latency, error rate
- [ ] Alert fires when bot CPU > 80%

---

### ISSUE #202: Add Comprehensive Logging to Database Methods

**Type:** Observability / Instrumentation
**Priority:** P1
**Impact:** High (SQL debugging)
**Effort:** Medium (10-12 hours)
**Dependencies:** None
**Risk Level:** Low

**Description:**

`bot/bot/database/methods/*.py` currently has 0 logging. Cannot debug SQL issues, understand slow queries, or track DB operation patterns.

**Subtasks:**
- [ ] Add logging to `bot/bot/database/methods/get.py` (2.5h)
- [ ] Add logging to `bot/bot/database/methods/insert.py` (2.5h)
- [ ] Add logging to `bot/bot/database/methods/update.py` (2.5h)
- [ ] Add logging to `bot/bot/database/methods/delete.py` (2.5h)

**Pattern for each method:**
```python
import time
log = logging.getLogger(__name__)

async def get_user(session, tgid):
    start = time.perf_counter()
    try:
        log.debug("event=db.query table=users operation=select tgid=%s", tgid)
        result = await session.execute(...)
        user = result.scalar()
        duration_ms = (time.perf_counter() - start) * 1000
        if duration_ms > 100:
            log.warning("event=db.slow_query table=users duration_ms=%.1f", duration_ms)
        return user
    except Exception as e:
        log.error("event=db.error table=users operation=select tgid=%s", tgid, exc_info=e)
        raise
```

---

### ISSUE #203: Instrument Conversion Funnel Events

**Type:** Analytics / Product
**Priority:** P1
**Impact:** High (enables growth decisions)
**Effort:** Medium (6-8 hours)
**Dependencies:** ConversionEventsMiddleware already exists
**Risk Level:** Low

**Description:**

ConversionEventsMiddleware logs conversion events, but no dashboard to visualize them. Need to:
1. Parse logs into structured data
2. Store in analytics database (or ElasticSearch)
3. Build real-time funnel dashboard

**Subtasks:**
- [ ] Setup log aggregation (ELK or Loki) (2h)
- [ ] Parse conversion events from logs (1h)
- [ ] Create event schema (0.5h)
- [ ] Build Grafana funnel dashboard (2h)
- [ ] Add retention analysis dashboard (2h)

**Events to Track:**
- `conv.start` → `conv.connect_click` → `conv.pay_open` → `conv.pre_checkout`
- Also: abandonment points, retry patterns

---

## EPIC 3: AUTO-FAILOVER & RESILIENCE — Week 3-4

### Why This Epic Matters
Single server failing = 100% downtime. Need automatic, instant failover with zero user impact.

### Impact
- Uptime: 95% → 99.5%+
- User experience: no connection drops on server failure
- OPS load: reduce manual intervention

---

### ISSUE #301: Implement Server Health Checking & Auto-Removal

**Type:** Feature / Reliability
**Priority:** P1
**Impact:** High
**Effort:** Large (8-10 hours)
**Dependencies:** Observability (ISSUE #201)
**Risk Level:** Medium

**Description:**

Servers can fail silently (OOM, network issues). Need continuous health checks and automatic removal of unhealthy servers.

**Requirements:**
- Check server every 10 seconds
- Measure latency + packet loss
- Remove server if: offline > 30 sec OR latency > 5s OR packet loss > 20%
- Log every state change
- Alert ops team

**Subtasks:**
- [ ] Create bot/misc/server_health_check.py (3h):
  ```python
  class ServerHealthMonitor:
      async def check_server(self, server_id, connection_endpoint):
          # Ping server
          # Measure latency
          # Measure packet loss
          # Return: healthy|degraded|unhealthy
  ```

- [ ] Integrate into bot startup (2h):
  ```python
  # bot/bot/main.py:
  asyncio.create_task(server_health_monitor.start_checks())
  ```

- [ ] NATS publisher for health status (2h)
- [ ] Auto-removal handler (2h):
  ```python
  async def on_server_unhealthy(server_id):
      # Remove from user key assignments
      # Reassign users to healthy servers
      # Log event
      # Alert ops
  ```

- [ ] Test with simulated failure (1h)

---

### ISSUE #302: Implement User Key Auto-Reassignment

**Type:** Feature / Reliability
**Priority:** P1
**Impact:** High
**Effort:** Medium (6-8 hours)
**Dependencies:** ISSUE #301 (server health detection)
**Risk Level:** Medium

**Description:**

When server fails, all users with keys on that server lose connection. Need to automatically reassign them to healthy servers.

**Subtasks:**
- [ ] Find all users with keys on unhealthy server (1h)
- [ ] Generate new keys on healthy server (1h)
- [ ] Update user in DB (0.5h)
- [ ] Send notification to user (1h):
  ```text
  "We moved your VPN to a faster server. No action needed!"
  ```
- [ ] Measure reassignment latency (1h)

**Acceptance Criteria:**
- [ ] User reassignment completes in < 10 seconds
- [ ] User's connection drops for < 30 seconds
- [ ] User receives in-app notification

---

## EPIC 4: UX OPTIMIZATION & CONVERSION — Week 3-4

### Why This Epic Matters
Trial → Paid conversion is THE growth lever. Small UX improvements = 10-20% revenue gains.

### Impact
- Trial→Paid conversion: 3-5% → 10-12% (3-4x improvement)
- Revenue: 2x from same user base
- User satisfaction: 4.0/5.0 → 4.5/5.0

---

### ISSUE #401: Implement UX Fixes from AI Agent

**Type:** Feature / Product
**Priority:** P1
**Impact:** Critical (growth)
**Effort:** Large (13-17 hours)
**Dependencies:** docs/ux/fix_plan.md (exists)
**Risk Level:** Low

**Description:**

UX Audit Agent generated `docs/ux/fix_plan.md` with prioritized fixes. Implement them.

From agent findings: **Top 3 UX problems**
1. Trial activation takes 5+ taps, users drop off at 3rd tap (target: < 3 taps)
2. Payment flow shows only 1 payment method (target: show 3+, let user choose)
3. No countdown timer on trial expiry (users don't realize time passing)

**Subtasks:**
- [ ] Implement trial activation 1-tap (3h):
  ```python
  # Remove: Location selection → Store server prompt
  # Use: Auto-select best server (by latency) → Skip to key delivery screen
  ```

- [ ] Add payment method selector (2h):
  ```python
  # Show: Stripe + PayPal + Cryptocurrency options
  # Let user pick (currently hidden behind provider API logic)
  ```

- [ ] Add trial countdown timer (1h):
  ```python
  # Display in main menu: "Trial expires in 5 days"
  ```

- [ ] Improve payment success notification (1h)
- [ ] A/B test: urgent vs calm messaging (3h)
- [ ] Measure conversion delta (2h)

**Acceptance Criteria:**
- [ ] Trial activation: 5+ taps → < 3 taps
- [ ] Payment method: 1 option → 3+ options visible
- [ ] Trial timer: shows countdown in main menu
- [ ] A/B test: runs for 1 week, measures conversion delta

---

### ISSUE #402: Setup A/B Testing Infrastructure

**Type:** Feature / Analytics
**Priority:** P1
**Impact:** High (enables experimentation)
**Effort:** Medium (6-8 hours)
**Dependencies:** ISSUE #203 (funnel tracking)
**Risk Level:** Low

**Description:**

Need mechanism to:
1. Assign users to experiment variants (A/B/C/etc)
2. Track which variant user is in
3. Measure outcome differences
4. Determine statistical significance

**Subtasks:**
- [ ] Create experiment configuration schema (1h)
- [ ] Implement user bucketing logic (2h):
  ```python
  def get_user_variant(user_tgid, experiment_name):
      # Hash(user_tgid + experiment) % 100
      # If 0-49: variant_a, 50-99: variant_b
      return variant
  ```

- [ ] Add experiment context to user session (1h)
- [ ] Track variant in all events (2h)
- [ ] Build experiment results dashboard (2h)

**Acceptance Criteria:**
- [ ] User consistently assigned to same variant across sessions
- [ ] All events include `experiment_variant` field
- [ ] Grafana dashboard shows:
  - Conversion rate by variant
  - Statistical significance (p-value)
  - Confidence interval

---

## EPIC 5: CHINA READINESS — Week 5-8

### Why This Epic Matters
China market = 3x potential users. But requires specialized protocols + network setup.

### Impact
- TAM expansion: 100M → 300M potential users
- Revenue opportunity: +30% MRR from China alone
- Technical complexity: high (protocol obfuscation, fallback domains)

---

### ISSUE #501: Add shadowsocks + obfs4 Protocol Stack

**Type:** Feature / Protocol
**Priority:** P1
**Impact:** Critical (China gateway)
**Effort:** Large (10-15 hours)
**Dependencies:** None (parallel with other work)
**Risk Level:** Medium

**Description:**

Great Firewall of China uses DPI (Deep Packet Inspection) to identify VPN traffic. shadowsocks + obfs4 obfuscate the traffic pattern.

**Subtasks:**
- [ ] Add shadowsocks server support (3h)
- [ ] Add obfs4 protocol (3h)
- [ ] Configure key generation for obfs4 (2h)
- [ ] Test from China IP (simulate with VPN to CN) (4h)
- [ ] Deploy to China-only server nodes (2h)

**Acceptance Criteria:**
- [ ] User can select "shadowsocks" or "obfs4" protocol
- [ ] Connection from CN IP: > 80% success rate
- [ ] Latency: < 200ms (95th percentile)

---

### ISSUE #502: Setup Backup Domain & Domain Fronting

**Type:** Infrastructure / Resilience
**Priority:** P1
**Impact:** High (China survival)
**Effort:** Large (8-10 hours)
**Dependencies:** None
**Risk Level:** Medium

**Description:**

China can block domains. Need 10+ backup domains so if primary is blocked, traffic flows through backup.

**Subtasks:**
- [ ] Register 5 secondary domains (.com, .org, .net, .io, .co) (1h, ops)
- [ ] Setup DNS round-robin across domains (2h)
- [ ] Implement domain rotation in client (2h):
  ```python
  # Try: primary.domain.com → backup1.domain.com → backup2.domain.com → ...
  ```

- [ ] Add domain fronting configuration (4h):
  ```python
  # Hide VPN traffic as HTTPS to content delivery network
  # Appears as normal CloudFlare request to GFW
  ```

- [ ] Test with GFW-like DPI simulator (2h)

**Acceptance Criteria:**
- [ ] 5+ backup domains functional
- [ ] Client auto-rotates if primary blocked
- [ ] Connection succeeds even if 3 domains are blocked

---

## EPIC 6: INFRASTRUCTURE SCALING — Week 6-8

### Why This Epic Matters
Current setup: single Redis, single NATS, single fastapi. Can't handle 10x traffic growth.

### Impact
- Ready for 10x user growth (50k → 500k+)
- Zero single points of failure
- Cost per user drops (better resource utilization)

---

### ISSUE #601: Redis Cluster Migration

**Type:** Infrastructure / Scaling
**Priority:** P1
**Impact:** High (required for multi-instance)
**Effort:** Large (8-10 hours)
**Dependencies:** ISSUE #301 (observability)
**Risk Level:** Medium

**Description:**

Current setup: single Redis instance. Need Redis Cluster for HA + scaling.

**Subtasks:**
- [ ] Deploy 3-node Redis Cluster (2h)
- [ ] Update FSM storage config (1h)
- [ ] Update cache config (1h)
- [ ] Test failover (node down, data still available) (2h)
- [ ] Load test: 10k concurrent users (2h)

**Acceptance Criteria:**
- [ ] Redis accessible via cluster endpoint
- [ ] Node failure: < 5 second recovery
- [ ] No data loss
- [ ] Performance: latency < 10ms (95th)

---

### ISSUE #602: NATS Cluster Setup

**Type:** Infrastructure / Scaling
**Priority:** P1
**Impact:** High (message bus reliability)
**Effort:** Large (8-10 hours)
**Dependencies:** None
**Risk Level:** Medium

**Description:**

Current: NATS single instance. Split into 3-node cluster.

**Subtasks:**
- [ ] Configure NATS cluster mode (2h)
- [ ] Update all client configs (1h)
- [ ] Test message persistence (2h)
- [ ] Test consumer failover (2h)
- [ ] Load test (2h)

---

## EPIC 7: DEVOPS AUTOMATION — Week 7-9

### Why This Epic Matters
Can't manually fix 100k users. Need bots to fix bots.

### Impact
- Incident resolution: 30 min → 30 sec
- On-call load: 80% reduction
- User perception: instant recovery

---

### ISSUE #701: Implement DevOps Automation Agent

**Type:** Feature / Automation
**Priority:** P2
**Impact:** High (operational efficiency)
**Effort:** Large (15-20 hours)
**Dependencies:** ISSUE #201 (observability)
**Risk Level:** Medium

**Description:**

Agent that:
1. Monitors Prometheus alerts
2. Runs diagnostic commands
3. Auto-fixes common issues
4. Escalates to humans if needed

**Common issues to auto-fix:**
- DB connection pool exhausted → restart bot
- NATS lag > 1000 messages → scale consumer workers
- Disk usage > 80% → cleanup logs
- Server timeout → mark unhealthy, reassign users

**Subtasks:**
- [ ] Create bot/agents/devops_agent.py (5h)
- [ ] Integration with Prometheus alerts (3h)
- [ ] Implement auto-fix commands (5h)
- [ ] Add human approval flow (3h)
- [ ] Test auto-fixes (3h)

---

### ISSUE #702: Setup Automated Incident Response

**Type:** Process / Automation
**Priority:** P2
**Impact:** High
**Effort:** Medium (6-8 hours)
**Dependencies:** ISSUE #701
**Risk Level:** Low

**Description:**

Runbook automation:
1. Alert fired → agent runs diagnostics
2. Agent gathers info (logs, metrics, status)
3. Agent suggests fix (or applies auto-fix)
4. Escalate to team if > X severity
5. Track resolution time + success

**Subtasks:**
- [ ] Create incident response runbook templates (2h)
- [ ] Implement alert → automation trigger (2h)
- [ ] Human approval UI (Slack bot or web dashboard) (2h)
- [ ] Metrics: MTTR, resolution success rate (1h)

---

## EPIC 8: AI AGENTS ACTIVATION — Week 7-9

### Why This Epic Matters
Built AI agents (UX, QA, Conversion analysts). Now activate them to drive growth systematically.

### Impact
- UX continuously improves (agent finds new issues weekly)
- QA catches bugs earlier (no dead-end flows)
- Conversion optimized through experimentation

---

### ISSUE #801: Enforce Callback Coverage Validation in CI/CD

**Type:** Process / QA
**Priority:** P2
**Impact:** Medium (bug prevention)
**Effort:** Small (2-3 hours)
**Dependencies:** check_callbacks.py (exists)
**Risk Level:** Low

**Description.**

QA agent generated callback index. Now make validation mandatory in CI/CD.

**Subtasks:**
- [ ] Update scripts/qa.sh to fail if unhandled callbacks (1h)
- [ ] Add to GitHub Actions workflow (0.5h)
- [ ] Document callback naming conventions (1h)

**Acceptance Criteria:**
- [ ] PR cannot merge if callback validation fails
- [ ] Error message points to exact unhandled callback
- [ ] Developer can run locally: `./scripts/qa.sh`

---

### ISSUE #802: Execute Conversion A/B Experiments from Agent

**Type:** Feature / Growth
**Priority:** P2
**Impact:** High (revenue growth)
**Effort:** Medium (8-10 hours)
**Dependencies:** ISSUE #402 (A/B framework)
**Risk Level:** Low

**Description:**

Conversion agent identified 5 high-impact experiments. Implement and measure them.

**Experiments:**
1. **Onboarding copy** (RU vs EN tone) → target: +5% signups
2. **Trial length** (3 days vs 7 days) → target: +10% conversion
3. **Payment CTA** (urgent: "Limited offer expires soon" vs normal) → target: +8% conversion
4. **Server selector** (auto-selected best vs user chooses) → target: +3%
5. **Referral reward** ($1 vs $2 vs $5) → target: measure elasticity

**Subtasks:**
- [ ] Implement experiment 1-2 (2-3h each)
- [ ] Run A/A test (verify bucketing works) (1h)
- [ ] Launch experiment 1 at 10% traffic (0.5h)
- [ ] Monitor for 1 week, measure significance (1h)
- [ ] Rollout winner to 100% (0.5h)
- [ ] Repeat for experiments 3-5 (monthly cadence)

**Acceptance Criteria:**
- [ ] Each experiment runs for 1 week min
- [ ] Sample size: 1k+ users per variant
- [ ] Statistical significance: p < 0.05
- [ ] Winner deployed to 100% if significant

---

## BACKLOG SUMMARY

| Epic | Issues | P0 | P1 | P2 | Total Effort | Timeline |
|------|--------|----|----|----|----|----------|
| 1: Stabilize | 5 | 5 | 0 | 0 | 21h | W1-2 |
| 2: Observability | 3 | 0 | 3 | 0 | 20h | W2-3 |
| 3: Auto-Failover | 2 | 0 | 2 | 0 | 18h | W3-4 |
| 4: UX & Conversion | 2 | 0 | 2 | 0 | 21h | W3-4 |
| 5: China Ready | 2 | 0 | 2 | 0 | 25h | W5-8 |
| 6: Scaling | 2 | 0 | 2 | 0 | 20h | W6-8 |
| 7: DevOps Automation | 2 | 0 | 1 | 1 | 27h | W7-9 |
| 8: AI Agents | 2 | 0 | 0 | 2 | 12h | W7-9 |
| **TOTAL** | **20** | **5** | **12** | **3** | **164h** | **9 weeks** |

**Recommended Allocation:**
- Week 1-2: Full team on Epic 1 (stabilize)
- Week 2-3: Split team (Epic 1 finish + Epic 2 start)
- Week 3-4: Parallel (Epics 2, 3, 4)
- Week 5+: Epics 5, 6, 7, 8 (longer, lower urgency)

---

**See also:** `docs/checklists/CHECKLISTS_BY_DOMAIN.md` (detailed implementation checklists)

---

## Epic 9+ (Growth Expansion)

> Merged from `ROADMAP_GROWTH_EXECUTION_2026-02-24.md` Part 2 (2026-02-26 consolidation).
> Labels: `epic`, `growth`, `ux`, `china`, `reliability`, `payments`

### EPIC 9: Funnel + Conversion Engine

**Goal:** Measurable trial→paid funnel with A/B experiments. Impact: +20–40% revenue at same traffic.

**Issue 9.1 — Add funnel event taxonomy + baseline dashboard**
- Priority: P0 | Effort: M | Risk: Low
- Subtasks: define event list in `docs/analytics/funnel_events.md`; ensure middleware emits `event=conv.*` for `/start`, connect click, help open, pay open, pre_checkout; add grep-based measurement commands.
- Acceptance: ≥5 funnel events in logs per real session. Verify: `docker compose logs vpn_hub_bot | rg "event=conv\." | head`

**Issue 9.2 — Improve /start UX: 3-day trial CTA + "Connect VPN" as primary**
- Priority: P0 | Effort: S | Risk: Low | Dependencies: localization strings
- Subtasks: update RU/EN copy in `bot/bot/locale/**/bot.po`; primary connect CTA first in main menu.
- Acceptance: MTFC decreases vs baseline; conv logs show connect click rate increasing.

**Issue 9.3 — Payment UX: Pending state + retry copy**
- Priority: P1 | Effort: M | Risk: Medium | Dependencies: payment webhook idempotency
- Subtasks: add "pending" microcopy and retry CTA; ensure duplicate webhook is idempotent across providers.
- Acceptance: payment support tickets decrease; log rate of `payment.*error` drops.

---

### EPIC 10: Self-healing + SLO-Driven Reliability

**Goal:** Reduce restart loops, improve MTTR. Impact: less churn, lower support load.

**Issue 10.1 — Distributed single-leader protection (replace /tmp lock)**
- Priority: P1 | Effort: M | Risk: Medium | Dependencies: Redis or NATS KV
- Subtasks: implement leader election via Redis (SETNX) or NATS KV; ensure only one polling instance runs.
- Acceptance: 2 replicas do not conflict. See also: `GITHUB_ISSUES_BACKLOG.md` Issue #104.

---

### EPIC 11: China Readiness (Growth)

**Goal:** Connection works under DPI and blocks (CN-first). Impact: TAM expansion, viral spread.

**Issue 11.1 — Protocol fallback ladder (CN)**
- Priority: P1 | Effort: L | Risk: High | Dependencies: `bot/bot/misc/VPN/**`
- Subtasks: define ladder (VLESS/Reality → Shadowsocks/obfs → Outline); add "Try another protocol" UX after failure; instrument success/failure per protocol.
- Acceptance: CN connect success improves measurably vs baseline.

**Issue 11.2 — Domain/port rotation strategy spec**
- Priority: P2 | Effort: M | Risk: Medium | Dependencies: infra/DNS
- Subtasks: create inventory doc and runbook steps; add monitoring and test plan from CN IP.
- Acceptance: rotation can be performed in <30 minutes.
