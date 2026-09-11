#!/usr/bin/env bash
# One-time (idempotent) Garage cluster bootstrap: single-node layout, media
# bucket, and an access key with the credentials from .env.
#
# Run from the HOST after `docker compose up -d garage`:
#   set -a; source .env; set +a
#   bash engine/infra/garage/init.sh
#
# This execs the `garage` binary directly inside the running `garage`
# container (docker compose exec runs the binary, not a shell — the image is
# distroless and has neither), so it reuses the server's own node identity
# and config; no RPC host/secret juggling needed from the outside.
set -euo pipefail

# Git Bash on Windows rewrites leading-/ arguments (like /garage) into Windows
# paths before they reach docker. This disables that; harmless on Linux/macOS.
export MSYS_NO_PATHCONV=1

COMPOSE="docker compose"
SVC="garage"

# Strips ANSI colour codes that garage's CLI always emits (even non-tty),
# which otherwise break naive grep/awk parsing of its output.
clean() { sed -E 's/\x1b\[[0-9;]*[a-zA-Z]//g'; }

run() { $COMPOSE exec -T "$SVC" /garage "$@" | clean; }

: "${GARAGE_MEDIA_BUCKET:?set GARAGE_MEDIA_BUCKET in .env}"
: "${GARAGE_ACCESS_KEY_ID:?set GARAGE_ACCESS_KEY_ID in .env}"
: "${GARAGE_SECRET_ACCESS_KEY:?set GARAGE_SECRET_ACCESS_KEY in .env}"

echo "[garage-init] waiting for node to report status..."
STATUS=""
for i in $(seq 1 30); do
  if STATUS=$(run status 2>&1); then
    break
  fi
  sleep 2
done
echo "${STATUS}"

NODE_ID=$(echo "${STATUS}" | awk '/==== HEALTHY NODES ====/{found=1; next} found && NF && $1 != "ID" {print $1; exit}')
if [ -z "${NODE_ID:-}" ]; then
  echo "[garage-init] could not determine node id from 'garage status'" >&2
  exit 1
fi
echo "[garage-init] node id: ${NODE_ID}"

LAYOUT=$(run layout show)
if echo "${LAYOUT}" | grep -q "No nodes currently have a role"; then
  echo "[garage-init] assigning single-node layout"
  run layout assign -z dc1 -c 100G "${NODE_ID}"
  CUR_VERSION=$(echo "${LAYOUT}" | grep -oE 'layout version: [0-9]+' | awk '{print $NF}')
  NEXT_VERSION=$((${CUR_VERSION:-0} + 1))
  run layout apply --version "${NEXT_VERSION}"
else
  echo "[garage-init] layout already assigned, skipping"
fi

if ! run bucket list | grep -qw "${GARAGE_MEDIA_BUCKET}"; then
  echo "[garage-init] creating bucket ${GARAGE_MEDIA_BUCKET}"
  run bucket create "${GARAGE_MEDIA_BUCKET}"
else
  echo "[garage-init] bucket ${GARAGE_MEDIA_BUCKET} already exists"
fi

if ! run key list | grep -q "${GARAGE_ACCESS_KEY_ID}"; then
  echo "[garage-init] importing access key"
  run key import "${GARAGE_ACCESS_KEY_ID}" "${GARAGE_SECRET_ACCESS_KEY}" -n now-media-app --yes
else
  echo "[garage-init] access key already imported"
fi

echo "[garage-init] granting read/write/owner on ${GARAGE_MEDIA_BUCKET} to ${GARAGE_ACCESS_KEY_ID}"
run bucket allow --read --write --owner "${GARAGE_MEDIA_BUCKET}" --key "${GARAGE_ACCESS_KEY_ID}"

echo "[garage-init] done. bucket info:"
run bucket info "${GARAGE_MEDIA_BUCKET}"
