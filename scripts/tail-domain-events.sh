#!/usr/bin/env bash
#
# Watch the domain-event stream while you use the app.
#
#   scripts/tail-domain-events.sh              # follow new events
#   scripts/tail-domain-events.sh --all        # replay everything first, then follow
#
# WHY THIS EXISTS. `publishDomainEvent` never throws — deliberately, so a Redis
# outage cannot block an editor's save. The cost is that its absence cannot
# either: with no `REDIS_URL` it logs, returns false, and the entire event path
# is inert with nothing anywhere saying so.
#
# Local development ran that way for months. The result was a publish hook that
# has been announcing `article.unpublished` every time an autosave fired over a
# published article — a false event, as old as the hook — which could not be
# observed until the transport was wired in production and someone read the
# stream by hand. A bug that only production can reveal is a bug production
# will reveal.
#
# So: wiring `REDIS_URL` into dev is half the fix. This is the other half. A
# wired bus nobody watches is most of the way back to the same blind spot —
# the events are delivered, and still nobody finds out what they say.
#
# Use it by putting it beside the editor: open an article, let autosave run,
# and see what the engine is actually told you did.

set -uo pipefail

STREAM="${DOMAIN_EVENT_STREAM:-now:domain-events:stream}"
CONTAINER="${REDIS_CONTAINER:-now-redis}"

if ! docker inspect "$CONTAINER" >/dev/null 2>&1; then
  echo "no container '$CONTAINER' — start the stack first (docker compose up -d redis)" >&2
  exit 2
fi

# The password lives in the container's own environment, so this needs no copy
# of it on the host and nothing secret is ever printed.
redis() { docker exec -i "$CONTAINER" sh -lc 'redis-cli -a "$REDIS_PASSWORD" --no-auth-warning "$@"' _ "$@" 2>/dev/null; }

pretty() {  # reads raw XREAD/XRANGE output, prints one line per event
  python3 -c '
import json, re, sys
for raw in sys.stdin:
    raw = raw.strip()
    if not raw.startswith("{"):
        continue
    try:
        e = json.loads(raw)
    except json.JSONDecodeError:
        print("  (unparseable) " + raw[:120]); continue
    name = e.get("event", "?")
    site = e.get("site_slug", "?")
    eid  = e.get("entity_id", "?")
    when = e.get("occurred_at", "")[11:23]
    print(f"  {when}  {name:<26} {site}/{eid}")
' 2>/dev/null || sed 's/^/  /'
}

last="\$"
if [ "${1:-}" = "--all" ]; then
  echo "--- everything already on $STREAM ---"
  redis XRANGE "$STREAM" - + | pretty
  last="0"
  echo "--- following ---"
else
  echo "following $STREAM (use --all to replay first). Ctrl-C to stop."
fi

# BLOCK 0 waits indefinitely rather than spinning, so this costs nothing while
# idle and reports the moment an event lands.
while true; do
  out="$(redis XREAD BLOCK 0 COUNT 10 STREAMS "$STREAM" "$last")"
  [ -z "$out" ] && continue
  echo "$out" | pretty
  # Advance past what we just read; ids are the lines shaped 1789626278751-0.
  newest="$(echo "$out" | grep -oE '^[0-9]{13}-[0-9]+$' | tail -1)"
  [ -n "$newest" ] && last="$newest"
done
