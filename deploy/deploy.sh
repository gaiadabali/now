#!/usr/bin/env bash
#
# NOW! Engine — deploy driver for the VPS. See docs/DEPLOY.md.
#
#   deploy/deploy.sh --pull                 # roll out IMAGE_TAG from .env
#   deploy/deploy.sh --pull --tag sha-abc123
#   deploy/deploy.sh --rollback sha-abc123  # no migration, no build
#   deploy/deploy.sh --status
#
# This exists instead of a README full of `docker compose` lines because a
# rollout has an order and a verification step, and both are easy to skip by
# hand at exactly the wrong moment.
#
# Four images, not six: the CMS and the commerce console were merged into the
# reader app at /team-editor (docs/ADMIN-CONSOLIDATION.md Phase 4), so
# `cms-jakarta`, `cms-bali` and `console` no longer exist as services.
#
# It never builds. Images come from GHCR — `next build` is the memory-hungry
# step that gets OOM-killed on a small box, with an error that reads like a
# code fault rather than a capacity one.
#
# It never touches the postgres volume, and a rollback does not reverse
# migrations. Undoing a migration is a separate, deliberate act.

set -Eeuo pipefail

DEPLOY_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$DEPLOY_DIR/.." && pwd)"
COMPOSE=(docker compose -f "$DEPLOY_DIR/docker-compose.yml" --env-file "$DEPLOY_DIR/.env")

# Ordered so a dependency is healthy before its dependents are asked to
# start. compose's depends_on already encodes this; naming it again here
# keeps the log readable when something stalls.
SERVICES=(postgres redis engine-api engine-worker web-jakarta web-bali)

die()  { printf '\n\033[31merror:\033[0m %s\n' "$*" >&2; exit 1; }
info() { printf '\033[36m==>\033[0m %s\n' "$*"; }
ok()   { printf '\033[32m  ok\033[0m %s\n' "$*"; }

usage() { sed -n '3,18p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit "${1:-0}"; }

MODE=""
TAG_OVERRIDE=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --pull)     MODE="deploy"; shift ;;
    --rollback) MODE="rollback"; TAG_OVERRIDE="${2:-}"; shift 2 || die "--rollback needs a tag" ;;
    --tag)      TAG_OVERRIDE="${2:-}"; shift 2 || die "--tag needs a value" ;;
    --status)   MODE="status"; shift ;;
    -h|--help)  usage 0 ;;
    *)          die "unknown argument: $1 (try --help)" ;;
  esac
done
[[ -n "$MODE" ]] || usage 1

[[ -f "$DEPLOY_DIR/.env" ]] || die "no deploy/.env — copy deploy/.env.example and fill it in"

if [[ "$MODE" == "status" ]]; then
  "${COMPOSE[@]}" ps
  exit 0
fi

# ---------------------------------------------------------------------------
# Resolve and validate the tag before anything is pulled or stopped.
# ---------------------------------------------------------------------------
set -a; # shellcheck disable=SC1091
source "$DEPLOY_DIR/.env"; set +a
[[ -n "$TAG_OVERRIDE" ]] && IMAGE_TAG="$TAG_OVERRIDE"

[[ -n "${IMAGE_TAG:-}" ]] || die "IMAGE_TAG is empty — set it in .env or pass --tag"
[[ "$IMAGE_TAG" != "latest" ]] || die "IMAGE_TAG=latest is refused: a rollback must be able to name what it rolls back to"
for v in POSTGRES_IMAGE API_IMAGE WORKER_IMAGE WEB_IMAGE; do
  [[ -n "${!v:-}" ]] || die "$v is empty — see deploy/.env.example"
done
export IMAGE_TAG

info "tag $IMAGE_TAG"

# ---------------------------------------------------------------------------
# The checkout must match the tag being deployed.
#
# Not every deployed file lives in the image. `<slug>/site/site.config.json`
# is BIND-MOUNTED from this checkout (see docker-compose.yml, web-jakarta),
# deliberately, so a brand or navigation change is a restart rather than a
# rebuild. The cost of that choice is a silent failure mode: pulling a new
# image without pulling the repo leaves new code reading old config, and the
# symptom is not an error. It is a footer missing the links the build added,
# or a favicon falling back to the wordmark — a worse page that still returns
# 200, which is exactly the kind of thing that survives a smoke test.
#
# Tags are `sha-<short sha>`, so the check is free and offline: the tag names
# the commit the image was built from, and HEAD must be that commit.
# ---------------------------------------------------------------------------
if [[ "$IMAGE_TAG" == sha-* ]] && git -C "$REPO_ROOT" rev-parse --git-dir >/dev/null 2>&1; then
  want="${IMAGE_TAG#sha-}"
  have="$(git -C "$REPO_ROOT" rev-parse HEAD 2>/dev/null)"
  if [[ "$have" != "$want"* ]]; then
    die "this checkout is not the commit being deployed
  image tag : $IMAGE_TAG  (built from $want)
  checkout  : ${have:0:${#want}}
  The city config under <slug>/site/ is mounted from here, not baked into the
  image, so deploying now would run new code against old config.
  Fix:  git -C $REPO_ROOT fetch origin && git -C $REPO_ROOT checkout $want"
  fi
  ok "checkout matches $IMAGE_TAG"
fi

# ---------------------------------------------------------------------------
# Pull every image FIRST. A partial rollout — new API against an old CMS —
# is worse than no rollout, so nothing stops until all four are on disk.
# ---------------------------------------------------------------------------
info "pulling images"
for img in "$POSTGRES_IMAGE" "$API_IMAGE" "$WORKER_IMAGE" "$WEB_IMAGE"; do
  docker pull --quiet "$img:$IMAGE_TAG" >/dev/null \
    || die "cannot pull $img:$IMAGE_TAG
  - is CI green for this SHA? see the publish-images workflow
  - are you logged in?  docker login ghcr.io -u <user> -p <PAT with read:packages>
    The packages are private and inherit the repo's visibility; a token from
    an account that cannot see gaiadabali's packages will fail here even if
    it can read the repository."
  ok "$img:$IMAGE_TAG"
done

# ---------------------------------------------------------------------------
# Roll out.
# ---------------------------------------------------------------------------
if [[ "$MODE" == "rollback" ]]; then
  info "ROLLBACK to $IMAGE_TAG — no migrations are run or reversed"
fi

info "starting services"
"${COMPOSE[@]}" up -d --remove-orphans "${SERVICES[@]}"

# ---------------------------------------------------------------------------
# Verify. A deploy that silently half-worked is the thing this guards.
# ---------------------------------------------------------------------------
info "waiting for health"
deadline=$(( SECONDS + 240 ))
for svc in postgres redis engine-api; do
  cid="$("${COMPOSE[@]}" ps -q "$svc")"
  [[ -n "$cid" ]] || die "$svc did not start"
  while :; do
    state="$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "$cid")"
    case "$state" in
      healthy|running) ok "$svc $state"; break ;;
      starting)        : ;;
      *)               die "$svc is $state — docker logs $cid" ;;
    esac
    (( SECONDS < deadline )) || die "$svc never became healthy — docker logs $cid"
    sleep 5
  done
done

# The API answering /healthz is the real proof: it means uvicorn is up and
# the platform pool was constructed. A container merely "running" is not.
api_port="${API_HOST_PORT:-4310}"
if ! curl -fsS --max-time 10 "http://127.0.0.1:${api_port}/healthz" >/dev/null; then
  die "engine-api is not answering /healthz on 127.0.0.1:${api_port}
  If the container is healthy but this fails, the port is published somewhere
  else — check API_HOST_PORT in .env against \`ss -tlnp\`."
fi
ok "engine-api /healthz"

for pair in "web-jakarta:${WEB_JAKARTA_HOST_PORT:-4311}" "web-bali:${WEB_BALI_HOST_PORT:-4315}"; do
  svc="${pair%%:*}"; port="${pair##*:}"
  # Any HTTP response is enough here: a Next/Payload route may legitimately
  # answer 3xx or 4xx at /, and this check is "is the server listening",
  # not "is the content right".
  if curl -fsS -o /dev/null --max-time 15 "http://127.0.0.1:${port}/" \
     || curl -s -o /dev/null -w '%{http_code}' --max-time 15 "http://127.0.0.1:${port}/" | grep -qE '^[2345]'; then
    ok "$svc responding on ${port}"
  else
    die "$svc is not responding on 127.0.0.1:${port} — docker compose logs $svc"
  fi
done

printf '\n\033[32mdeployed\033[0m %s\n' "$IMAGE_TAG"
printf 'rollback with: deploy/deploy.sh --rollback <previous tag>\n'
