#!/usr/bin/env bash
# site:create <slug> — provision a city DB, migrate it, seed it, register it
# in the platform `sites` roster, and scaffold <slug>/{site,cms,content}/.
#
# Thin wrapper: all real logic lives in now_db.provisioning (Python), so the
# CLI behaves identically whether invoked from bash, PowerShell, or CI.
# Requires `now-db` (and its `now-platform-db` dependency) to be installed —
# see engine/packages/db/README.md.
#
# Usage:
#   scripts/site-create.sh <slug> --hostname <host> --name <name> [options]
#
# Connection env vars (see engine/packages/db/README.md for defaults):
#   NOW_PG_HOST, NOW_PG_PORT, NOW_PG_USER, NOW_PG_PASSWORD
#   NOW_PLATFORM_DATABASE_URL (overrides the above for the platform DB)
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [ $# -lt 1 ]; then
  echo "usage: $0 <slug> --hostname <host> --name <name> [--locale en] [--timezone Asia/Jakarta] [--currency IDR] [--module <name> ...]" >&2
  exit 2
fi

exec python -m now_db.cli create "$@"
