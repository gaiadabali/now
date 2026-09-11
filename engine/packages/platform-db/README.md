# now-platform-db

Alembic-owned `engine` schema for `now_platform`: the `sites` registry,
orgs, partnerships (+ audit), campaigns, placements, the `ad_events`
ledger, facets/terms, identities, user_profiles, itineraries, and
syndications.

## Why everything is under `engine`, not `public`

ARCHITECTURE.md §2's topology diagram shows `now_platform.public` eventually
owned by a Payload instance (sites/orgs/campaigns/placements alongside
partner users). That instance doesn't exist yet, and no task in
PROGRESS.md's wave plan currently schedules building it. Per the E0.2 task
brief: "own both schemas conceptually in now_platform, but only create
engine there; a Payload instance will own platform public later." So every
table in this package's baseline migration lives in `now_platform.engine` —
nothing here creates a `public` table, and moving a table to `public` later
is a follow-up migration (`ALTER TABLE ... SET SCHEMA`), not a rewrite.

**Fixed external contract** (do not change without updating consumers —
`now_config.SiteConfig` in `engine/packages/config`, `engine-api`'s site
resolution, `now-db`'s `site:create`):

```sql
sites(id, slug, hostname, name, locale, timezone, currency,
      brand_tokens jsonb, nav jsonb, home_rails jsonb,
      ranking_weights jsonb, db_ref text, enabled_modules text[], status)
```

## Install (dev)

```bash
pip install -e engine/packages/platform-db
```

## Connection env vars

| Var | Default | Used for |
|---|---|---|
| `NOW_PLATFORM_DATABASE_URL` | built from the vars below | full DSN override |
| `NOW_PG_HOST` | `localhost` | host |
| `NOW_PG_PORT` | `5432` | port |
| `NOW_PG_USER` | `now` | role |
| `NOW_PG_PASSWORD` | `now` | password |

Mirrors `now_db.settings` exactly (see that package's README) — the two are
kept as separate, non-importing modules on purpose; they target different
databases and have no other reason to share code.

## CLI

```bash
now-platform-db migrate                      # idempotent
now-platform-db hash [--write-baseline]
now-platform-db check                        # exit 1 on drift from schema_baseline.json
now-platform-db ensure-partitions [--days-ahead 7]     # engine.ad_events
now-platform-db drop-old-partitions --retention-days <n>
```

## Rollout notes

- `ad_events` is the billing ledger (ARCHITECTURE.md §11) and is
  RANGE-partitioned by day, same pattern as the city DB's
  `interactions`/`impressions`. It is append-only by convention in this
  wave — no role/grant enforcement yet (see `now-db`'s README, "Notes for
  later waves"). Do not `UPDATE`/`DELETE` rows in it.
- `0001`'s `downgrade()` drops every table it created, in dependency order.
  Safe against an empty database; do not run it against a platform DB with
  real partnership/campaign/itinerary data without a backup.
- Cross-database references (`partnerships.place_id`, `itinerary_stops.place_id`,
  `syndications.origin_article_id` — all pointing at a row in some city DB)
  are plain `uuid` columns with **no foreign key**. Postgres cannot enforce
  a constraint across databases, and DB-per-city means the referenced row
  lives elsewhere by design. Referential integrity for these is an
  application/worker responsibility, not the database's.

## Notes for later waves

- When a Payload instance for `now_platform.public` is built, moving
  `sites`/`orgs`/`campaigns`/`placements` there (if that's still the plan)
  is a migration that does `ALTER TABLE engine.x SET SCHEMA public`, run
  once `public` exists, plus updating every consumer's assumed schema.
  Until then, treat `now_platform.engine` as authoritative for all of it.
- `engine.partnerships` / `engine.campaigns` / `engine.placements` carry a
  `site_id` and are logically tenant-scoped even though they live in one
  shared database (unlike the DB-per-city split). No RLS is applied in this
  wave — DB-per-city already isolates the highest-value tenancy boundary
  (content), and adding RLS here would require agreeing a session-variable
  convention with `engine-api` (E0.3) that hasn't been specified yet.
  Revisit when the partner console (E4.4) needs enforceable per-partner
  row access, not before.
