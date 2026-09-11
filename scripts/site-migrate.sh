#!/usr/bin/env bash
# site:migrate — apply the now-db migration set to one or every registered
# city DB. Idempotent: a second run applies nothing new.
#
# Usage:
#   scripts/site-migrate.sh --all              # every non-disabled city
#   scripts/site-migrate.sh --url <dsn-or-db>  # exactly one target
set -euo pipefail

if [ $# -lt 1 ]; then
  echo "usage: $0 --all | --url <dsn-or-db-name>" >&2
  exit 2
fi

exec python -m now_db.cli migrate "$@"
