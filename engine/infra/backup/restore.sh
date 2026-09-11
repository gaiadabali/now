#!/usr/bin/env bash
# Restores one database from a pg_dump custom-format dump produced by
# backup.sh. DESTRUCTIVE: drops and recreates the target database.
#
# Usage:
#   set -a; source .env; set +a
#   bash engine/infra/backup/restore.sh now_jakarta ./backups/now_jakarta-latest.dump
set -euo pipefail

COMPOSE="docker compose"
PG_SVC="postgres"

DB="${1:?usage: restore.sh <database> <dump-file>}"
DUMP="${2:?usage: restore.sh <database> <dump-file>}"

: "${POSTGRES_USER:?POSTGRES_USER must be set (source .env first)}"

if [ ! -f "${DUMP}" ]; then
  echo "[restore] dump file not found: ${DUMP}" >&2
  exit 1
fi

case " now_platform now_jakarta now_bali " in
  *" ${DB} "*) : ;;
  *) echo "[restore] refusing unknown database '${DB}'" >&2; exit 1 ;;
esac

echo "[restore] this will DROP and recreate '${DB}'. Ctrl+C within 5s to abort."
sleep 5

echo "[restore] terminating existing connections to ${DB}"
$COMPOSE exec -T "${PG_SVC}" psql -U "${POSTGRES_USER}" -d postgres -c \
  "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '${DB}' AND pid <> pg_backend_pid();"

echo "[restore] dropping and recreating ${DB}"
$COMPOSE exec -T "${PG_SVC}" psql -U "${POSTGRES_USER}" -d postgres -c "DROP DATABASE IF EXISTS ${DB};"
$COMPOSE exec -T "${PG_SVC}" psql -U "${POSTGRES_USER}" -d postgres -c "CREATE DATABASE ${DB};"
$COMPOSE exec -T "${PG_SVC}" psql -U "${POSTGRES_USER}" -d "${DB}" -c \
  "CREATE EXTENSION IF NOT EXISTS vector; CREATE EXTENSION IF NOT EXISTS postgis;"

echo "[restore] restoring dump into ${DB}"
$COMPOSE exec -T "${PG_SVC}" pg_restore -U "${POSTGRES_USER}" -d "${DB}" --no-owner --no-privileges < "${DUMP}"

echo "[restore] done. row counts by schema:"
$COMPOSE exec -T "${PG_SVC}" psql -U "${POSTGRES_USER}" -d "${DB}" -c \
  "SELECT schemaname, count(*) FROM pg_tables WHERE schemaname IN ('public','engine') GROUP BY schemaname;"
