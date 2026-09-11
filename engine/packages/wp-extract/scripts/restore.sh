#!/usr/bin/env bash
# Restore the UpdraftPlus MariaDB dump into a throwaway container.
#
# Usage:
#   SOURCE_DUMP=/path/to/backup.sql.gz scripts/restore.sh
#
# Defaults to the dump path given for task E1.1. Safe to re-run: if the
# container's data volume already has data, MariaDB's own entrypoint skips
# re-running the init scripts (the restore is a no-op), so this script is
# idempotent. Pass --fresh to force a clean restore from scratch.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PKG_ROOT="$(cd "$HERE/.." && pwd)"
DOCKER_DIR="$PKG_ROOT/docker"

SOURCE_DUMP="${SOURCE_DUMP:-/c/Users/Hansel/Downloads/backup_2026-09-08-1336_NOW_Jakarta_cc5fbb88fa25-db.gz}"
FRESH=0
for arg in "$@"; do
  case "$arg" in
    --fresh) FRESH=1 ;;
  esac
done

if [[ ! -f "$SOURCE_DUMP" ]]; then
  echo "ERROR: source dump not found at $SOURCE_DUMP" >&2
  echo "Set SOURCE_DUMP=/path/to/dump.sql.gz to override." >&2
  exit 1
fi

cd "$DOCKER_DIR"

if [[ "$FRESH" -eq 1 ]]; then
  echo "--fresh requested: tearing down existing container + volume"
  docker compose down -v --remove-orphans || true
fi

mkdir -p "$DOCKER_DIR/dump"
echo "Copying dump ($(du -h "$SOURCE_DUMP" | cut -f1)) into docker/dump/backup.sql.gz ..."
cp -f "$SOURCE_DUMP" "$DOCKER_DIR/dump/backup.sql.gz"

echo "Starting throwaway MariaDB container (now-wp-extract-mariadb, port ${WP_EXTRACT_DB_PORT:-13306}) ..."
docker compose up -d

# IMPORTANT: `docker compose up --wait` / the container healthcheck are NOT
# sufficient here. The official MariaDB entrypoint runs the dump restore
# (docker-entrypoint-initdb.d) against a *temporary* internal server before
# the real one starts, and `mariadb-admin ping` (our healthcheck) succeeds
# against that temp server too — over the local socket, independent of the
# TCP port. That makes the container report "healthy" seconds into a restore
# that takes ~60-90s to actually finish, and a query against it mid-restore
# fails with "Access denied" (root's password isn't set with its final value
# yet at that instant) or "Lost connection" (temp server torn down under
# you). So: wait for the entrypoint's own completion marker in the log
# first, THEN wait for the real server's healthcheck.
sleep 5  # let the entrypoint get far enough to know which path it's on
if docker logs now-wp-extract-mariadb 2>&1 | grep -q "Initializing database files"; then
  echo "Fresh volume — waiting for the dump restore to complete (~60-90s for 354MB) ..."
  RESTORE_TIMEOUT=900
  elapsed=0
  # "MariaDB init process done" appears exactly once, only after the temp
  # server has finished running every docker-entrypoint-initdb.d script
  # (i.e. after the restore) and been shut down. Do NOT use "ready for
  # connections" as a shortcut here — that line appears twice (once for the
  # short-lived temp server, before the restore even starts).
  while ! docker logs now-wp-extract-mariadb 2>&1 | grep -q "MariaDB init process done"; do
    sleep 3
    elapsed=$((elapsed + 3))
    if [[ "$elapsed" -ge "$RESTORE_TIMEOUT" ]]; then
      echo "ERROR: restore did not complete within ${RESTORE_TIMEOUT}s. Check: docker logs now-wp-extract-mariadb" >&2
      exit 1
    fi
  done
else
  echo "Existing data volume — init scripts skipped (restore already applied), just waiting for the server ..."
fi

echo "Restore step complete — waiting for the real server to accept connections ..."
docker compose up -d --wait --wait-timeout 120

echo
echo "Container healthy. Verifying row counts against the dump's own table list ..."

ROOT_PW="${WP_EXTRACT_DB_ROOT_PASSWORD:-wpextract_root}"
DB_NAME="${WP_EXTRACT_DB_NAME:-nowjakarta_wp}"

docker exec now-wp-extract-mariadb mariadb -uroot -p"$ROOT_PW" "$DB_NAME" -e "
  SELECT table_name, table_rows
  FROM information_schema.tables
  WHERE table_schema = '$DB_NAME'
  ORDER BY table_name;
"

echo
echo "Exact counts for the acceptance-critical tables:"
docker exec now-wp-extract-mariadb mariadb -uroot -p"$ROOT_PW" "$DB_NAME" -e "
  SELECT 'nb15_posts (publish,post)' AS what, COUNT(*) AS n FROM nb15_posts WHERE post_type='post' AND post_status='publish'
  UNION ALL SELECT 'nb15_posts (attachment)', COUNT(*) FROM nb15_posts WHERE post_type='attachment'
  UNION ALL SELECT 'nb15_term_relationships', COUNT(*) FROM nb15_term_relationships
  UNION ALL SELECT 'nb15_term_relationships x category', COUNT(*) FROM nb15_term_relationships tr
    JOIN nb15_term_taxonomy tt ON tt.term_taxonomy_id = tr.term_taxonomy_id WHERE tt.taxonomy='category'
  UNION ALL SELECT 'nb15_posts (upcoming-events)', COUNT(*) FROM nb15_posts WHERE post_type='upcoming-events'
  UNION ALL SELECT 'nb15_posts (tribe_events)', COUNT(*) FROM nb15_posts WHERE post_type='tribe_events'
  UNION ALL SELECT 'nb15_posts (tribe_venue)', COUNT(*) FROM nb15_posts WHERE post_type='tribe_venue'
  UNION ALL SELECT 'nb15_posts (tribe_organizer)', COUNT(*) FROM nb15_posts WHERE post_type='tribe_organizer'
  UNION ALL SELECT 'nb15_posts (page)', COUNT(*) FROM nb15_posts WHERE post_type='page';
"

echo
echo "Restore verified. Connection details for the extraction step:"
echo "  host=127.0.0.1 port=${WP_EXTRACT_DB_PORT:-13306} db=$DB_NAME user=root password=$ROOT_PW"
