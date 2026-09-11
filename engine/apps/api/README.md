# engine-api

One FastAPI deployment serving every NOW! city. Site is resolved from the
request path (`/v1/{site}/...`), mapped to a lazily-created, pooled
connection to that city's database. See ARCHITECTURE.md §2, §3.5, §16.

## Layout

```
app/
  api/
    root.py          non-tenant routes (/healthz)
    v1/
      router.py       aggregates every /v1/{site}/... route group
      health.py        GET /v1/{site}/health
  domain/             empty module packages reserved for later waves
    articles/ places/ search/ itineraries/ events/ assistant/
  infra/
    db/
      pools.py         CityPoolRegistry — one AsyncEngine per city, lazy + cached
      registry.py      SiteRegistryCache — TTL-cached view over `sites`
      deps.py          get_city_db / get_platform_db — the router itself
    logging/
      setup.py          JSON log formatter
      middleware.py      per-request request_id/site/latency logging
    auth/
      api_key.py        require_api_key — interim, file-backed key store
    ratelimit/
      limiter.py         Redis-backed, degrades to in-process
      deps.py            enforce_rate_limit dependency
  main.py             create_app() factory + lifespan wiring
  config.py           Settings (pydantic-settings)
openapi/
  export_openapi.py  dumps app.openapi() to openapi.json, no server needed
client/
  package.json        openapi-typescript + tsc, `npm run generate` / `typecheck`
tests/
  seed/                throwaway-Postgres seed SQL mirroring E0.2's real schema
```

`engine/packages/config/` (`now_config`) holds the `SiteConfig` model and
`SiteConfigLoader` — reusable by `engine-worker` and `web` later, not just
this API.

## The Depends() contract

```python
from app.infra.db.deps import get_city_db, get_platform_db

@router.get("/whatever")
async def handler(site: str, db: AsyncSession = Depends(get_city_db)) -> ...:
    ...  # db is bound to the correct city's pool for `site`

@router.get("/platform-thing")
async def handler2(db: AsyncSession = Depends(get_platform_db)) -> ...:
    ...  # db is bound to the single shared platform pool
```

Both dependencies read shared state off `request.app.state` (set up once in
`create_app`'s lifespan), not module-level globals — this is what lets tests
build independent `FastAPI` instances against different databases without
leaking pooled connections between them.

`get_city_db` behavior:

| Condition | Result |
|---|---|
| Unknown site slug | `404` |
| Site registered but `status != 'active'` | `404` (not a valid routing target yet) |
| Site registry (platform DB) unreachable | `503` |
| Site's own city DB unreachable | `503`, pool cache **not** evicted |
| Otherwise | yields an `AsyncSession` bound to that city's pool |

## Site registry contract (fixed by E0.2, confirmed against the real migration)

```
engine.sites(id uuid, slug, hostname, name, locale, timezone, currency,
             brand_tokens jsonb, nav jsonb, home_rails jsonb,
             ranking_weights jsonb, db_ref text, enabled_modules text[],
             status text CHECK IN ('active','provisioning','disabled'))
```

Table lives in the platform DB's `engine` schema — **not** `public` and
**not** unqualified `sites`. `now_config.loader` queries `engine.sites`
explicitly; do not remove the schema qualifier, the connecting role's
`search_path` is not guaranteed to include `engine`.

`db_ref` is a bare database name in the common case (e.g. `now_bandung`) —
every city lives on the same Postgres instance (ARCHITECTURE.md §2) — or a
full DSN, passed through untouched. This is the exact same convention
`engine/packages/db`'s `city_database_url()` independently uses (verified
by reading its `settings.py`), so the two packages agree without having to
import from each other.

## Registry cache

`SiteRegistryCache` (app/infra/db/registry.py) caches `sites` rows for
`ENGINE_API_SITE_REGISTRY_CACHE_TTL_SECONDS` (default 30s). A new site, or
an edited/disabled one, is picked up within that window — **no restart, no
redeploy**. `cache.invalidate(slug)` / `invalidate_all()` are the
documented invalidation hook for anything that wants it sooner.

Verified live: inserted a new `sites` row into a running server and it
started serving `/v1/{new-slug}/health` after the TTL elapsed, no restart —
see the PR/task notes for the exact transcript.

## City pool cache

`CityPoolRegistry` (app/infra/db/pools.py) creates one `AsyncEngine` per
city slug on first use and caches it. A connectivity failure does **not**
evict the cached engine — `pool_pre_ping=True` lets SQLAlchemy recover on
its own once the DB comes back; rebuilding the whole pool on every failed
request would be far more expensive than one failed `SELECT`. Only
`db_ref` itself changing (a site repointed at a different database) evicts
and rebuilds that site's pool.

## Auth (interim — flagged for the schema owner)

`app/infra/auth/api_key.py` provides `Depends(require_api_key)`: a site-
scoped `X-API-Key` header check. Keys are sha256-hashed and configured via
a JSON file (`ENGINE_API_API_KEYS_FILE`, shape
`{"<site-slug>": ["<sha256-hex>", ...]}`) rather than a database table,
because the `sites` row shape fixed for this task has no key column and
creating an `api_keys` table is a schema decision for the senior-db seat,
not this one. Swapping in a DB-backed store later is a drop-in replacement
for `ApiKeyStore` — no call-site changes. **Not wired to any route yet** —
no business/beacon endpoint exists in this wave to protect.

## Rate limiting

`app/infra/ratelimit/limiter.py`: fixed-window counter in Redis
(`ENGINE_API_REDIS_URL`) when reachable, falling back to an in-process
per-worker counter (logs one warning) when Redis is unset, unreachable, or
errors mid-request. `Depends(enforce_rate_limit)` is available but, like
auth, not yet attached to a route.

## Logging

JSON lines on stdout, one per request, via `RequestContextMiddleware`:
`request_id` (echoed back as `X-Request-Id`), `site` (parsed from
`/v1/{site}/...`, `null` for non-tenant routes), `path`, `method`,
`status_code`, `latency_ms`. Example:

```json
{"ts": "2026-09-08T16:44:13", "level": "INFO", "logger": "engine_api.request",
 "message": "request completed", "request_id": "9ef4900e-...", "site": "epsilon",
 "path": "/v1/epsilon/health", "method": "GET", "status_code": 200, "latency_ms": 80.42}
```

## Running locally

```bash
cd engine/apps/api
uv sync --extra dev

export ENGINE_API_PLATFORM_DATABASE_URL="postgresql+asyncpg://now:now@localhost:5432/now_platform"
export ENGINE_API_CITY_DB_HOST=localhost
export ENGINE_API_CITY_DB_PORT=5432
export ENGINE_API_CITY_DB_USER=now
export ENGINE_API_CITY_DB_PASSWORD=now

uv run uvicorn app.main:app --reload
```

## Testing

Tests need a real Postgres — no mocking of SQLAlchemy/asyncpg. Spin a
throwaway instance and seed it with the fixed contract shape:

```bash
docker run -d --name now-e03-pg \
  -e POSTGRES_USER=now -e POSTGRES_PASSWORD=now -e POSTGRES_DB=now_platform \
  -p 55510:5432 postgres:16

psql -h localhost -p 55510 -U now -d now_platform -f tests/seed/schema.sql
psql -h localhost -p 55510 -U now -d now_platform -c "CREATE DATABASE now_alpha;"
psql -h localhost -p 55510 -U now -d now_platform -c "CREATE DATABASE now_beta;"
psql -h localhost -p 55510 -U now -d now_platform -f tests/seed/sites.sql
psql -h localhost -p 55510 -U now -d now_alpha -c "CREATE TABLE marker (city TEXT); INSERT INTO marker VALUES ('alpha');"
psql -h localhost -p 55510 -U now -d now_beta  -c "CREATE TABLE marker (city TEXT); INSERT INTO marker VALUES ('beta');"

uv run pytest -v
```

`tests/seed/*.sql` uses synthetic slugs (`alpha`, `beta`, `gamma-provisioning`,
`delta-unreachable`) rather than real city names, on purpose — real city
names must never appear as literals under `engine/` (ARCHITECTURE.md §3.5),
including in test fixtures.

## OpenAPI -> TypeScript client

```bash
uv run python openapi/export_openapi.py     # writes openapi/openapi.json
cd client && npm install
npm run generate    # openapi-typescript -> src/schema.ts
npm run typecheck    # tsc --noEmit
```

Wired in CI: `.github/workflows/engine-api-openapi-client.yml` regenerates
both and fails the build if the committed `openapi.json` / `schema.ts` are
stale. `.github/workflows/engine-api-tests.yml` runs the pytest suite
against a services: postgres container and greps for `jakarta`/`bali`
literals under `engine/`.

## Notes / follow-ups for later waves

- **E0.5 (beacon endpoint) -- done.** `app/api/v1/events.py` implements
  `POST /events` and `OPTIONS /events`, registered in `app/api/v1/router.py`;
  business logic lives in `app/domain/events/`. **Not** `Depends(require_api_key)`
  as originally sketched here -- PROGRESS.md decision C2 supersedes that (a
  key shipped in public client JS is not a secret; the beacon sends no auth
  header at all). Protection is a CORS origin allowlist sourced from the
  site registry's `hostname` (`app/domain/events/cors.py`) plus rate
  limiting keyed by the payload's `anon_id` (not the IP-based
  `enforce_rate_limit` above, which stays unused by this endpoint).
- **API key storage**: interim JSON-file store (see above). If/when an
  `api_keys` table is added to the platform schema, only
  `app/infra/auth/api_key.py`'s `ApiKeyStore` needs a new implementation.
- **Negative-lookup caching**: `SiteRegistryCache` does not cache "unknown
  slug" results, so a flood of requests for nonexistent sites each hit the
  platform DB. Not a problem at this scale; worth a short negative-TTL if
  it ever becomes one.
- Python 3.13 was used for local development/verification (3.12 was
  unavailable in this environment); `pyproject.toml` still declares
  `requires-python = ">=3.12"` per the task's stack spec, and nothing here
  uses a 3.13-only feature.
