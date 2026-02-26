#!/usr/bin/env bash
# =============================================================================
# VPNHub — Postgres backup script (P0.5)
#
# USAGE
#   bash scripts/backup/postgres_backup.sh [--dry-run]
#
# WHAT IT DOES
#   1. Runs pg_dump inside the running postgres_db_container using
#      docker exec (no extra credentials needed beyond the running container).
#   2. Writes a custom-format archive (.dump) to /backups inside the
#      container, which is bind-mounted from the host at
#      /opt/vpnhub/backups/postgres (set via BACKUP_HOST_DIR below).
#   3. Deletes .dump files older than RETENTION_DAYS (default 14).
#   4. Exits non-zero on any failure.
#
# ENVIRONMENT (override via env or bot/.env — never hardcode here)
#   POSTGRES_USER   — defaults to "vpnhub"
#   POSTGRES_DB     — defaults to "VPNHubBotDB"
#   BACKUP_HOST_DIR — host path for backup files (default /opt/vpnhub/backups/postgres)
#   RETENTION_DAYS  — days to keep backups (default 14)
#   CONTAINER_NAME  — docker container name (default postgres_db_container)
# =============================================================================

set -euo pipefail

# ---------------------------------------------------------------------------
# Config — sourced from env; never from git-tracked secrets
# ---------------------------------------------------------------------------
POSTGRES_USER="${POSTGRES_USER:-vpnhub}"
POSTGRES_DB="${POSTGRES_DB:-VPNHubBotDB}"
BACKUP_HOST_DIR="${BACKUP_HOST_DIR:-/opt/vpnhub/backups/postgres}"
RETENTION_DAYS="${RETENTION_DAYS:-14}"
CONTAINER_NAME="${CONTAINER_NAME:-postgres_db_container}"
CONTAINER_BACKUP_DIR="/backups"  # inside container (bind-mounted from BACKUP_HOST_DIR)

TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
DUMP_FILENAME="vpnhubdb_${TIMESTAMP}.dump"
DUMP_PATH="${CONTAINER_BACKUP_DIR}/${DUMP_FILENAME}"

DRY_RUN=0
[[ "${1:-}" == "--dry-run" ]] && DRY_RUN=1

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"; }
die() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] ERROR: $*" >&2; exit 1; }

# ---------------------------------------------------------------------------
# Pre-flight checks
# ---------------------------------------------------------------------------
log "=== VPNHub Postgres Backup ==="
log "Container : ${CONTAINER_NAME}"
log "Database  : ${POSTGRES_DB}"
log "User      : ${POSTGRES_USER}"
log "Backup dir: ${BACKUP_HOST_DIR}"
log "Retention : ${RETENTION_DAYS} days"
log "Filename  : ${DUMP_FILENAME}"
[[ "${DRY_RUN}" -eq 1 ]] && log "DRY RUN — no files will be written" && exit 0

command -v docker >/dev/null 2>&1 || die "docker not found in PATH"

# Check container is running
if ! docker inspect --format '{{.State.Running}}' "${CONTAINER_NAME}" 2>/dev/null | grep -q '^true$'; then
    die "Container '${CONTAINER_NAME}' is not running. Start it first with: docker compose up -d db_postgres"
fi

# Ensure host backup directory exists
if [[ ! -d "${BACKUP_HOST_DIR}" ]]; then
    log "Creating backup directory: ${BACKUP_HOST_DIR}"
    mkdir -p "${BACKUP_HOST_DIR}" || die "Cannot create ${BACKUP_HOST_DIR}. Run as root or pre-create the directory."
fi

# Verify bind mount is active (container must see /backups as a directory)
if ! docker exec "${CONTAINER_NAME}" test -d "${CONTAINER_BACKUP_DIR}"; then
    die "Container does not have ${CONTAINER_BACKUP_DIR} mounted. " \
        "Add the bind mount to docker-compose.yml and recreate the container."
fi

# ---------------------------------------------------------------------------
# Run pg_dump inside container
# ---------------------------------------------------------------------------
log "Starting pg_dump (custom format)..."

docker exec \
    --env PGPASSWORD="" \
    "${CONTAINER_NAME}" \
    pg_dump \
        --username="${POSTGRES_USER}" \
        --dbname="${POSTGRES_DB}" \
        --format=custom \
        --compress=6 \
        --no-password \
        --file="${DUMP_PATH}" \
    || die "pg_dump failed"

# Verify the file was actually written and is non-empty
HOST_DUMP="${BACKUP_HOST_DIR}/${DUMP_FILENAME}"
if [[ ! -s "${HOST_DUMP}" ]]; then
    die "Dump file '${HOST_DUMP}' is missing or empty after pg_dump"
fi

DUMP_SIZE="$(du -sh "${HOST_DUMP}" | cut -f1)"
log "Backup written: ${HOST_DUMP} (${DUMP_SIZE})"

# ---------------------------------------------------------------------------
# Retention — delete .dump files older than RETENTION_DAYS
# ---------------------------------------------------------------------------
log "Applying retention policy: removing backups older than ${RETENTION_DAYS} days..."
DELETED=0
while IFS= read -r -d '' old_file; do
    log "  Deleting: ${old_file}"
    rm -f "${old_file}"
    DELETED=$((DELETED + 1))
done < <(find "${BACKUP_HOST_DIR}" -maxdepth 1 -name "vpnhubdb_*.dump" \
         -mtime "+${RETENTION_DAYS}" -print0)

log "Retention: removed ${DELETED} old backup(s)"

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
REMAINING=$(find "${BACKUP_HOST_DIR}" -maxdepth 1 -name "vpnhubdb_*.dump" | wc -l)
log "=== Backup complete. ${REMAINING} backup(s) on disk. ==="
