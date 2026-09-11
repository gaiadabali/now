# NOW! Engine — infra stack

Owns: `engine/infra/**`, `docker-compose.yml`, `docker-compose.override.yml`,
`.env.example`. See `ARCHITECTURE.md` §2 (Topology), §3.5 (Site separation)
and §14 (Media) for the design this implements.

This stack ships the **infrastructure layer** for E0.1: Postgres (pgvector +
PostGIS, three databases), Redis, Garage (S3-compatible object store),
imgproxy, and Caddy. Application services (`engine-api`, `engine-worker`,
`cms-jakarta`, `cms-bali`, `web`, `console`) are wired into
`docker-compose.yml` as placeholders behind the `apps` compose profile — they
don't have Dockerfiles yet (other tasks own those), so they're defined (env,
healthchecks, `depends_on`) but not started by a plain `docker compose up`.

---

## First-time setup

1. **Copy the env template and fill in secrets:**

   ```bash
   cp .env.example .env
   ```

   Generate every `changeme-*` value:

   ```bash
   openssl rand -hex 32        # *_SECRET / *_KEY (hex)
   openssl rand -base64 32     # *_TOKEN (base64)
   ```

   `GARAGE_ACCESS_KEY_ID` must start with `GK` (Garage's expected prefix).

   If you're running this on a machine that already has something bound to
   `5432` or `6379` (a local Postgres/Redis install), change
   `POSTGRES_PORT` / `REDIS_PORT` in `.env` — the containers still listen on
   the standard ports internally, only the host-side publish changes.

2. **Bring up the infra services:**

   ```bash
   docker compose up -d
   ```

   This builds the Postgres image (pgvector + PostGIS layered on top of
   `pgvector/pgvector:pg16`) and starts postgres, redis, garage, imgproxy,
   caddy. First boot takes ~10–30s to go healthy; watch it with:

   ```bash
   docker compose ps
   ```

   All five should reach `healthy`. `depends_on: condition: service_healthy`
   is wired throughout, so anything you add on top (including the `apps`
   profile services) won't start against a half-initialized dependency.

3. **Bootstrap the Garage cluster (one-time, per environment):**

   Garage's image is distroless (no shell), so its own container can't run
   an init script. Bootstrap runs from the host instead, executing the
   `garage` binary directly inside the running container via
   `docker compose exec` (which doesn't need a shell):

   ```bash
   set -a; source .env; set +a
   bash engine/infra/garage/init.sh
   ```

   This assigns the single-node cluster layout, creates the
   `GARAGE_MEDIA_BUCKET` bucket, imports `GARAGE_ACCESS_KEY_ID` /
   `GARAGE_SECRET_ACCESS_KEY` as a Garage access key, and grants it
   read/write/owner on the bucket. It's idempotent — safe to re-run after a
   redeploy; it skips steps that are already done.

   On Windows Git Bash, the script sets `MSYS_NO_PATHCONV=1` itself so
   `/garage` isn't rewritten into a Windows path — no action needed.

4. **Verify the Postgres extensions:**

   ```bash
   for db in now_platform now_jakarta now_bali; do
     docker compose exec -T postgres psql -U "$POSTGRES_USER" -d "$db" \
       -c "SELECT extname, extversion FROM pg_extension WHERE extname IN ('vector','postgis');"
   done
   ```

   Both `vector` and `postgis` should show up in all three databases —
   they're enabled by `engine/infra/postgres/init/01-create-databases.sh` on
   first cluster init (the standard `docker-entrypoint-initdb.d` mechanism,
   so it only runs once against a fresh `postgres-data` volume).

5. **Local HTTPS / hostnames:** the `.env.example` defaults route Caddy at
   `*.now.localhost` / `*.localhost`. Caddy issues these certs from its own
   internal CA automatically — curl with `-k` (skip verification) or
   `--resolve host:443:127.0.0.1` for smoke tests, no `/etc/hosts` changes
   needed for `*.localhost` on most resolvers. Production: set the real
   `*_HOSTNAME` vars (`nowjakarta.co.id` etc., see `.env.example`) and Caddy
   gets public ACME certs instead.

---

## Running

```bash
# infra only (default) — this is what `docker compose up` does
docker compose up -d

# infra + app placeholders, once those tasks have real Dockerfiles:
docker compose --profile apps up -d

# production (skip the local dev override — no host port publishing):
docker compose -f docker-compose.yml up -d
```

`docker-compose.override.yml` is dev-only: it publishes postgres/redis/
garage/imgproxy/caddy ports to `localhost` so you can hit them directly
without going through Caddy. It's picked up automatically by plain
`docker compose` commands; the `-f docker-compose.yml` form above skips it.

### Smoke-testing the media path (Garage → imgproxy → Caddy)

```bash
# upload a source image to Garage (path-style S3 API on :3900)
docker run --rm \
  -e AWS_ACCESS_KEY_ID="$GARAGE_ACCESS_KEY_ID" \
  -e AWS_SECRET_ACCESS_KEY="$GARAGE_SECRET_ACCESS_KEY" \
  --network now-net -v "$(pwd):/data" amazon/aws-cli:2.27.0 \
  --endpoint-url http://garage:3900 \
  s3 cp /data/some-image.png s3://now-media/media/some-image.png

# build a signed imgproxy URL (imgproxy signs with HMAC-SHA256(key, salt+path))
python3 - <<'EOF'
import hmac, hashlib, base64, binascii, os
key = binascii.unhexlify(os.environ["IMGPROXY_KEY"])
salt = binascii.unhexlify(os.environ["IMGPROXY_SALT"])
path = "/rs:fill:300:200/plain/s3://now-media/media/some-image.png@png"
sig = base64.urlsafe_b64encode(hmac.new(key, salt + path.encode(), hashlib.sha256).digest()).rstrip(b"=").decode()
print(f"/{sig}{path}")
EOF

# request it through Caddy (replace the path with the one printed above)
curl -k --resolve media.now.localhost:443:127.0.0.1 \
  "https://media.now.localhost/<signature>/rs:fill:300:200/plain/s3://now-media/media/some-image.png@png" \
  -o resized.png
```

Note: AWS CLI v2's high-level `s3 cp` *download* does a `HeadObject`
preflight that can 400 against Garage in some CLI versions — the fix is to
use `aws s3api get-object --bucket ... --key ...` for downloads (uploads via
`s3 cp` work fine). This is a client-side CLI quirk, not a Garage bug —
observed and worked around during E0.1 verification.

---

## Backing up

```bash
set -a; source .env; set +a
bash engine/infra/backup/backup.sh
```

Dumps all three databases with `pg_dump -Fc` (custom format, compressed,
restorable with `pg_restore`) into `${BACKUP_DIR:-./backups}/<db>-<UTC
timestamp>.dump`, plus a `<db>-latest.dump` pointer to the newest dump per
database.

Set `BACKUP_REMOTE_ENABLED=true` (plus `BACKUP_REMOTE_ENDPOINT`,
`BACKUP_REMOTE_BUCKET`, `BACKUP_REMOTE_ACCESS_KEY_ID`,
`BACKUP_REMOTE_SECRET_ACCESS_KEY` in `.env`) to also push each dump to an
S3-compatible remote — Cloudflare R2 or Backblaze B2 both work, since both
speak the S3 API. Point a cron entry or systemd timer at `backup.sh` for
scheduled backups; it's side-effect-free to run repeatedly (each run adds a
new timestamped dump, doesn't touch old ones).

Garage/media backup (object storage) is out of scope for E0.1 — Garage
supports remote-cluster replication for that when it's needed; not wired up
here.

## Restoring

```bash
set -a; source .env; set +a
bash engine/infra/backup/restore.sh now_jakarta ./backups/now_jakarta-latest.dump
```

**Destructive**: drops and recreates the named database, re-enables
`vector`/`postgis`, then `pg_restore`s the dump into it. Only accepts
`now_platform` / `now_jakarta` / `now_bali` as the target. Gives you 5
seconds to Ctrl+C before it terminates existing connections and drops the
database. Prints a row-count-by-schema summary at the end so you can eyeball
that something actually landed.

Verified during E0.1: seeded a probe row, ran `backup.sh`, dropped the
table, ran `restore.sh`, confirmed the probe row (and the pgvector/PostGIS
extensions) came back.

---

## Layout

```
engine/infra/
  postgres/
    Dockerfile              pgvector/pgvector:pg16 + postgresql-16-postgis-3
    init/01-create-databases.sh   creates now_platform/now_jakarta/now_bali, enables extensions
  garage/
    garage.toml              static config (secrets come from env, not this file)
    init.sh                   one-time cluster/bucket/key bootstrap (idempotent)
  caddy/
    Caddyfile                 routing per ARCHITECTURE.md §3.5
  backup/
    backup.sh                 pg_dump all 3 DBs, optional R2/B2 push
    restore.sh                 pg_restore one DB (destructive)
  scripts/
    healthcheck.sh             docker compose ps health summary, non-zero exit on any unhealthy
```

## Known deviations / things the next agent should know

- **Postgres base image changed from the obvious choice.** `postgis/postgis:16-*`
  is still built on Debian bullseye, whose `bullseye-security` apt repo has
  gone stale (`Release file ... is expired`) — `apt-get update` fails inside
  it as of this writing. Built the other direction instead:
  `pgvector/pgvector:pg16` (Debian bookworm, current) +
  `postgresql-16-postgis-3` from the same PGDG repo. Same two extensions,
  same behavior, just not EOL-adjacent.
- **Garage is distroless** (`dxflrs/garage:v1.3.1` has no shell, no
  `envsubst`, no `curl`). This ruled out an env-templated `garage.toml` and
  an in-container init entrypoint — hence the static config file (secrets
  via `GARAGE_RPC_SECRET`/`GARAGE_ADMIN_TOKEN`/`GARAGE_METRICS_TOKEN` env,
  which the `garage` binary reads as CLI-flag-equivalents) and the
  host-run `init.sh` that `docker compose exec`s the binary directly.
- **`docker compose up` (no args) only starts the infra layer**, by design —
  the app services don't have Dockerfiles yet. Once E0.3/CMS/web tasks land
  theirs, drop `profiles: ["apps"]` from the relevant service block in
  `docker-compose.yml` and fix its `build.context`.
- Root-level `.gitignore` doesn't exist yet in this repo (not part of my
  owned paths) — whoever adds one should include `.env` and `backups/`.
