#!/bin/sh
set -eu

POSTGRES_HOST="${POSTGRES_HOST:-db_postgres}"
POSTGRES_PORT="${POSTGRES_PORT:-5432}"
POSTGRES_USER="${POSTGRES_USER:-vpnhub}"
POSTGRES_DB="${POSTGRES_DB:-VPNHubBotDB}"
NATS_HTTP_URL="${NATS_HTTP_URL:-http://nats:8222/varz}"
WAIT_TIMEOUT="${WAIT_TIMEOUT:-120}"

start_ts="$(date +%s)"

echo "event=wait.postgres.start host=${POSTGRES_HOST} port=${POSTGRES_PORT}"
while true; do
  if pg_isready -h "${POSTGRES_HOST}" -p "${POSTGRES_PORT}" -U "${POSTGRES_USER}" -d "${POSTGRES_DB}" >/dev/null 2>&1; then
    echo "event=wait.postgres.ok"
    break
  fi
  now_ts="$(date +%s)"
  if [ $((now_ts - start_ts)) -ge "${WAIT_TIMEOUT}" ]; then
    echo "event=wait.postgres.timeout timeout=${WAIT_TIMEOUT}" >&2
    exit 1
  fi
  sleep 2
done

echo "event=wait.nats.start url=${NATS_HTTP_URL}"
while true; do
  if wget -q -O /dev/null "${NATS_HTTP_URL}"; then
    echo "event=wait.nats.ok"
    break
  fi
  now_ts="$(date +%s)"
  if [ $((now_ts - start_ts)) -ge "${WAIT_TIMEOUT}" ]; then
    echo "event=wait.nats.timeout timeout=${WAIT_TIMEOUT}" >&2
    exit 1
  fi
  sleep 2
done

echo "event=wait.done"
