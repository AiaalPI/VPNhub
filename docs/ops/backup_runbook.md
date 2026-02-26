# Postgres Backup Runbook (P0.5)

## How backups work

`scripts/backup/postgres_backup.sh` runs `pg_dump` inside the running
`postgres_db_container` via `docker exec`. The dump is written to `/backups`
inside the container, which is bind-mounted from `/opt/vpnhub/backups/postgres`
on the host (added in `docker-compose.yml` under `db_postgres.volumes`).

- **Format:** PostgreSQL custom archive (`.dump`, compressed at level 6).
  Custom format is smaller than plain SQL and supports parallel restore.
- **Filename:** `vpnhubdb_YYYYmmdd_HHMMSS.dump`
- **Retention:** 14 days (configurable via `RETENTION_DAYS` env var).
- **Credentials:** Inherited from the running container — no passwords in scripts.

---

## First-time setup on the host

Run once on the production server before the first `docker compose up`:

```bash
# Create the host backup directory
sudo mkdir -p /opt/vpnhub/backups/postgres
sudo chown $(whoami):$(whoami) /opt/vpnhub/backups/postgres

# Recreate db_postgres to activate the new bind mount
cd /opt/vpnhub
docker compose up -d --force-recreate db_postgres

# Verify the mount is visible inside the container
docker exec postgres_db_container ls /backups
# → (empty, no error)
```

---

## Manual backup

```bash
# From repo root (any environment with Docker)
bash scripts/backup/postgres_backup.sh

# Dry-run — prints config without writing anything
bash scripts/backup/postgres_backup.sh --dry-run

# Override retention or backup dir
RETENTION_DAYS=7 BACKUP_HOST_DIR=/tmp/test_backups bash scripts/backup/postgres_backup.sh
```

Expected output:

```
[2026-02-26 03:30:01] === VPNHub Postgres Backup ===
[2026-02-26 03:30:01] Container : postgres_db_container
[2026-02-26 03:30:01] Database  : VPNHubBotDB
[2026-02-26 03:30:01] Starting pg_dump (custom format)...
[2026-02-26 03:30:04] Backup written: /opt/vpnhub/backups/postgres/vpnhubdb_20260226_033001.dump (4.2M)
[2026-02-26 03:30:04] Applying retention policy: removing backups older than 14 days...
[2026-02-26 03:30:04] Retention: removed 0 old backup(s)
[2026-02-26 03:30:04] === Backup complete. 1 backup(s) on disk. ===
```

Verify the file:

```bash
ls -lah /opt/vpnhub/backups/postgres | tail -5
```

---

## Cron setup (recommended: daily at 03:30)

```bash
# Edit crontab as the deploy user (not root unless required)
crontab -e
```

Add:

```cron
30 3 * * * /bin/bash /opt/vpnhub/scripts/backup/postgres_backup.sh >> /opt/vpnhub/logs/backup.log 2>&1
```

To verify cron is running:

```bash
grep backup /var/log/syslog | tail -5          # Debian/Ubuntu
grep backup /var/log/cron | tail -5            # RHEL/CentOS
cat /opt/vpnhub/logs/backup.log | tail -20
```

### systemd timer (alternative to cron)

Create `/etc/systemd/system/vpnhub-backup.service`:

```ini
[Unit]
Description=VPNHub Postgres backup
After=docker.service

[Service]
Type=oneshot
User=ubuntu
WorkingDirectory=/opt/vpnhub
ExecStart=/bin/bash /opt/vpnhub/scripts/backup/postgres_backup.sh
StandardOutput=append:/opt/vpnhub/logs/backup.log
StandardError=append:/opt/vpnhub/logs/backup.log
```

Create `/etc/systemd/system/vpnhub-backup.timer`:

```ini
[Unit]
Description=VPNHub Postgres backup — daily at 03:30

[Timer]
OnCalendar=*-*-* 03:30:00
Persistent=true

[Install]
WantedBy=timers.target
```

Enable:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now vpnhub-backup.timer
sudo systemctl list-timers vpnhub-backup.timer
```

---

## Restore procedure (safe restore test)

> Run this against a **temporary database**, never against the live production DB.

### Step 1 — Create a temporary test database

```bash
docker exec -it postgres_db_container psql -U vpnhub -d postgres \
  -c "CREATE DATABASE vpnhubdb_restore_test;"
```

### Step 2 — Restore the dump into the test database

```bash
# Replace the filename with the dump you want to verify
DUMP_FILE="/opt/vpnhub/backups/postgres/vpnhubdb_20260226_033001.dump"

docker exec -i postgres_db_container \
  pg_restore \
    --username=vpnhub \
    --dbname=vpnhubdb_restore_test \
    --no-owner \
    --no-privileges \
    --exit-on-error \
    /backups/$(basename "${DUMP_FILE}")
```

### Step 3 — Sanity queries

```bash
docker exec -it postgres_db_container psql -U vpnhub -d vpnhubdb_restore_test <<'SQL'
SELECT COUNT(*) AS user_count FROM users;
SELECT COUNT(*) AS key_count  FROM keys;
SELECT COUNT(*) AS server_count FROM servers;
SELECT version_num FROM alembic_version;
SQL
```

Expected: row counts > 0 (for a live-data backup), `alembic_version` shows the head revision.

### Step 4 — Drop the test database

```bash
docker exec -it postgres_db_container psql -U vpnhub -d postgres \
  -c "DROP DATABASE vpnhubdb_restore_test;"
```

---

## Restore to production (emergency only)

> **Stop the bot first.** Never restore into a live, connected database.

```bash
# 1. Stop bot
docker compose stop vpn_hub_bot

# 2. Drop and recreate the production DB
docker exec -it postgres_db_container psql -U vpnhub -d postgres <<'SQL'
SELECT pg_terminate_backend(pid)
FROM pg_stat_activity
WHERE datname = 'VPNHubBotDB' AND pid <> pg_backend_pid();
DROP DATABASE "VPNHubBotDB";
CREATE DATABASE "VPNHubBotDB" OWNER vpnhub;
SQL

# 3. Restore from chosen dump
DUMP_FILE="vpnhubdb_20260226_033001.dump"
docker exec -i postgres_db_container \
  pg_restore \
    --username=vpnhub \
    --dbname=VPNHubBotDB \
    --no-owner \
    --no-privileges \
    --exit-on-error \
    /backups/${DUMP_FILE}

# 4. Restart bot
docker compose up -d vpn_hub_bot
```

---

## RPO / RTO

| Metric | Value |
|---|---|
| **RPO** (Recovery Point Objective) | 24 hours (daily cron). Reduce to hourly by adjusting crontab if needed. |
| **RTO** (Recovery Time Objective) | ~5–15 minutes (depends on DB size; typical VPNHub DB is <500 MB). |
| **Retention** | 14 days (configurable via `RETENTION_DAYS`). |
| **Backup location** | `/opt/vpnhub/backups/postgres` (host-local only). |
| **Off-site** | Not implemented (MVP). For off-site: pipe dump to `s3cmd put` or `rclone copy` after `pg_dump`. |

---

## Off-site backup (optional, S3-compatible)

To ship backups to S3 after writing locally, add to `postgres_backup.sh` after the dump:

```bash
# Requires: rclone configured with remote named "s3vpnhub"
if command -v rclone >/dev/null 2>&1; then
    rclone copy "${HOST_DUMP}" s3vpnhub:vpnhub-backups/postgres/ \
        && log "Uploaded to S3: ${DUMP_FILENAME}"
fi
```

`rclone` config is stored in `~/.config/rclone/rclone.conf` — never commit it.
