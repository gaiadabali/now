#!/usr/bin/env bash
# Summarizes docker-compose service health; exits non-zero if any service
# managed by this stack is not "healthy" (or not running at all). Intended
# for a cron/systemd-timer job that alerts on failure, or for CI smoke tests.
#
# Usage: bash engine/infra/scripts/healthcheck.sh
set -euo pipefail

COMPOSE="docker compose"
FAILED=0

SERVICES=$($COMPOSE ps --services)

for svc in ${SERVICES}; do
  CID=$($COMPOSE ps -q "${svc}")
  if [ -z "${CID}" ]; then
    echo "[healthcheck] ${svc}: NOT RUNNING"
    FAILED=1
    continue
  fi
  HEALTH=$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}no-healthcheck{{end}}' "${CID}")
  if [ "${HEALTH}" = "healthy" ] || [ "${HEALTH}" = "no-healthcheck" ]; then
    echo "[healthcheck] ${svc}: ${HEALTH}"
  else
    echo "[healthcheck] ${svc}: ${HEALTH}  <-- NOT HEALTHY"
    FAILED=1
  fi
done

exit "${FAILED}"
