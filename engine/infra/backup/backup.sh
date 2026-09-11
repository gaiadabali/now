#!/usr/bin/env bash
# Backs up all three Postgres databases (pg_dump custom format, one file
# each) to a local directory, then optionally pushes them to an S3-compatible
# remote (Cloudflare R2 or Backblaze B2 — both speak the S3 API) if
# BACKUP_REMOTE_ENABLED=true.
#
# Usage:
#   set -a; source .env; set +a
#   bash engine/infra/backup/backup.sh
#
# Local dumps land in ${BACKUP_DIR:-./backups}/<db>-<timestamp>.dump and are
# restorable with restore.sh (or plain `pg_restore`).
set -euo pipefail

COMPOSE="docker compose"
PG_SVC="postgres"
DATABASES=("now_platform" "now_jakarta" "now_bali")

: "${POSTGRES_USER:?POSTGRES_USER must be set (source .env first)}"
BACKUP_DIR="${BACKUP_DIR:-./backups}"
TIMESTAMP="$(date -u +%Y%m%dT%H%M%SZ)"

mkdir -p "${BACKUP_DIR}"

echo "[backup] dumping ${#DATABASES[@]} databases to ${BACKUP_DIR}"
DUMPED_FILES=()
for db in "${DATABASES[@]}"; do
  OUT="${BACKUP_DIR}/${db}-${TIMESTAMP}.dump"
  echo "[backup]   ${db} -> ${OUT}"
  $COMPOSE exec -T "${PG_SVC}" pg_dump -U "${POSTGRES_USER}" -Fc -d "${db}" > "${OUT}"
  DUMPED_FILES+=("${OUT}")
done

# Keep a "latest" pointer per db so restore.sh / operators don't need to
# guess the timestamp.
for db in "${DATABASES[@]}"; do
  LATEST="${BACKUP_DIR}/${db}-latest.dump"
  MATCH=$(ls -t "${BACKUP_DIR}/${db}-"*.dump 2>/dev/null | grep -v -- "-latest.dump" | head -1 || true)
  if [ -n "${MATCH}" ]; then
    cp "${MATCH}" "${LATEST}"
  fi
done

echo "[backup] local dumps complete:"
printf '  %s\n' "${DUMPED_FILES[@]}"

if [ "${BACKUP_REMOTE_ENABLED:-false}" = "true" ]; then
  : "${BACKUP_REMOTE_ENDPOINT:?BACKUP_REMOTE_ENDPOINT required when BACKUP_REMOTE_ENABLED=true}"
  : "${BACKUP_REMOTE_BUCKET:?BACKUP_REMOTE_BUCKET required when BACKUP_REMOTE_ENABLED=true}"
  : "${BACKUP_REMOTE_ACCESS_KEY_ID:?BACKUP_REMOTE_ACCESS_KEY_ID required when BACKUP_REMOTE_ENABLED=true}"
  : "${BACKUP_REMOTE_SECRET_ACCESS_KEY:?BACKUP_REMOTE_SECRET_ACCESS_KEY required when BACKUP_REMOTE_ENABLED=true}"

  echo "[backup] uploading to ${BACKUP_REMOTE_ENDPOINT}/${BACKUP_REMOTE_BUCKET}"
  for f in "${DUMPED_FILES[@]}"; do
    base=$(basename "${f}")
    docker run --rm \
      -e AWS_ACCESS_KEY_ID="${BACKUP_REMOTE_ACCESS_KEY_ID}" \
      -e AWS_SECRET_ACCESS_KEY="${BACKUP_REMOTE_SECRET_ACCESS_KEY}" \
      -v "$(cd "$(dirname "${f}")" && pwd)":/backups:ro \
      amazon/aws-cli:2.27.0 \
      --endpoint-url "${BACKUP_REMOTE_ENDPOINT}" \
      s3 cp "/backups/${base}" "s3://${BACKUP_REMOTE_BUCKET}/${base}"
  done
  echo "[backup] remote upload complete"
else
  echo "[backup] BACKUP_REMOTE_ENABLED != true, skipping remote upload"
fi
