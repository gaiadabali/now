#!/usr/bin/env bash
#
# Start both cities locally and run the full smoke test against them.
#
# Exists because verifying through Docker cost ~5 minutes a cycle and I spent
# far too many of them. `sharp` failing on Windows was the original reason
# this was not possible; the npm workspace dedupe fixed that, so the app runs
# natively now and a full check takes seconds.
#
# Run this BEFORE `docker build`, and before anything is pushed.
#
#   scripts/verify-local.sh              # build once, then verify
#   scripts/verify-local.sh --no-build   # reuse the existing .next
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WEB="$ROOT/engine/apps/web"
JKT_PORT=3420
BALI_PORT=3421

PG_PASSWORD="$(grep -E '^POSTGRES_PASSWORD=' "$ROOT/.env" | cut -d= -f2)"
PG="postgresql://now:${PG_PASSWORD}@localhost:15432"

export PLATFORM_DATABASE_URI="$PG/now_platform"
export PLATFORM_DATABASE_URL="$PG/now_platform"
export PAYLOAD_SECRET="${PAYLOAD_SECRET:-local-verify-secret}"
export NOW_REPO_ROOT="$ROOT"
export NEXT_TELEMETRY_DISABLED=1

pids=()
cleanup() {
  for pid in "${pids[@]:-}"; do kill "$pid" 2>/dev/null || true; done
  # next start spawns children; clear the ports explicitly on Windows.
  for port in "$JKT_PORT" "$BALI_PORT"; do
    for p in $(netstat -ano 2>/dev/null | grep ":$port" | grep LISTENING | awk '{print $NF}' | sort -u); do
      taskkill //F //PID "$p" >/dev/null 2>&1 || true
    done
  done
}
trap cleanup EXIT

if [ "${1:-}" != "--no-build" ]; then
  echo "==> building (once, for both cities)"
  ( cd "$WEB" && DATABASE_URI="$PG/now_jakarta" SITE_SLUG=jakarta npx next build ) \
    || { echo "BUILD FAILED"; exit 1; }
fi

# Free a port before binding it. Without this, a previous run's server keeps
# serving, the new one dies with EADDRINUSE, and the checks silently measure
# the OLD build — or, once the old one exits, nothing at all. Both happened:
# a stale CMS made a fixed build look broken, and an overlapping verify run
# made Bali's admin look dead when its server had simply never started.
free_port() {
  local port="$1"
  for p in $(netstat -ano 2>/dev/null | grep ":$port" | grep LISTENING | awk '{print $NF}' | sort -u); do
    taskkill //F //PID "$p" >/dev/null 2>&1 || true
  done
}

start_city() {
  local slug="$1" db="$2" port="$3"
  free_port "$port"
  ( cd "$WEB" && DATABASE_URI="$PG/$db" SITE_SLUG="$slug" PORT="$port" \
      npx next start -p "$port" > "/tmp/verify-$slug.log" 2>&1 ) &
  pids+=("$!")
}

echo "==> starting jakarta :$JKT_PORT and bali :$BALI_PORT"
start_city jakarta now_jakarta "$JKT_PORT"
start_city bali    now_bali    "$BALI_PORT"

for port in "$JKT_PORT" "$BALI_PORT"; do
  for _ in $(seq 1 40); do
    code="$(curl -s -o /dev/null -w '%{http_code}' --max-time 4 "http://127.0.0.1:$port/" 2>/dev/null)"
    [ "$code" != "000" ] && break
    sleep 2
  done
  if [ "$code" = "000" ]; then
    echo "  city on :$port never came up — see /tmp/verify-*.log"
    exit 1
  fi
done

# A server that failed to bind would otherwise be reported as a broken app.
# Check explicitly rather than inferring it from odd results.
for slug in jakarta bali; do
  if grep -q EADDRINUSE "/tmp/verify-$slug.log" 2>/dev/null; then
    echo "  $slug FAILED TO BIND (EADDRINUSE) — another server is on its port."
    echo "  Results would describe a different process. Aborting."
    exit 1
  fi
done

# Every route the nav and footer actually link to. A 500 here is a bug; a 404
# means something links at a page that does not exist, which is equally a bug
# because the link shipped.
echo
echo "==> routes"
route_fail=0
for port in "$JKT_PORT" "$BALI_PORT"; do
  city="jakarta"; [ "$port" = "$BALI_PORT" ] && city="bali"
  for route in / /dining /stay /wellness /things-to-do /events /guides /about /contact /advertise /podcast /subscribe /areas /culture /places /editorial /unclassified /search "/dining?page=3" "/unclassified?page=2"; do
    code="$(curl -s -o /dev/null -w '%{http_code}' --max-time 20 "http://127.0.0.1:$port$route")"
    if [ "$code" = "200" ]; then
      printf '  \033[32mok\033[0m   %-8s %-16s %s\n' "$city" "$route" "$code"
    else
      printf '  \033[31mFAIL\033[0m %-8s %-16s %s\n' "$city" "$route" "$code"
      route_fail=1
    fi
  done
done

echo
echo "==> smoke"
bash "$ROOT/scripts/smoke.sh" "http://127.0.0.1:$JKT_PORT" "http://127.0.0.1:$BALI_PORT"
smoke_status=$?

[ "$route_fail" -eq 0 ] && [ "$smoke_status" -eq 0 ]
