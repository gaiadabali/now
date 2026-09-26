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
  `interactions`/`impressions`. It is append-only by convention still —
  0017 gave `now_runtime` `SELECT, INSERT` on it (no `UPDATE`/`DELETE`) but
  did **not** add an RLS policy to it (see the "role split and RLS" note
  below for why). Do not `UPDATE`/`DELETE` rows in it regardless.
- `offer_events` (0012) is `ad_events`'s partitioned sibling and is granted
  the same way. Query it by its parent name, `engine.offer_events` — Postgres
  transparently routes to whichever daily child partition(s) the `WHERE ts
  ...` predicate needs, and `now_runtime`'s grant is on the parent, which
  Postgres also propagates to every existing and future child partition
  automatically. A query against one partition directly (`engine.
  offer_events_p2026_09_26`) does **not** inherit that grant — a partition
  is its own object as far as `GRANT`/`REVOKE` is concerned, so reading one
  by name needs its own grant, which nothing in this package issues. There
  is no product reason to query a partition directly; this is a note for
  whoever is tempted to, during an incident, before wondering why `now_runtime`
  can suddenly not read something it could read yesterday.
- `0001`'s `downgrade()` drops every table it created, in dependency order.
  Safe against an empty database; do not run it against a platform DB with
  real partnership/campaign/itinerary data without a backup. The same is
  true of every later migration's `downgrade()` in this package.
- Cross-database references (`partnerships.place_id`, `itinerary_stops.place_id`,
  `syndications.origin_article_id`, `destinations.place_id`,
  `offer_places.place_id`, and others added from migration 0012 onward —
  all pointing at a row in some city DB) are plain `text` columns with
  **no foreign key**. Postgres cannot enforce a constraint across
  databases, and DB-per-city means the referenced row lives elsewhere by
  design. Referential integrity for these is an application/worker
  responsibility, not the database's. `text`, never `uuid` —
  `scripts/check_no_payload_uuid_refs.py` is the CI gate for this (F69).

## Role split and RLS (migrations 0016/0017 — F7/F6)

- **Two roles beyond the historical single superuser**: `now_migrator`
  (runs migrations, owns every object in `engine`, `BYPASSRLS`) and
  `now_runtime` (what the application should connect as — no DDL rights on
  `engine`, no `BYPASSRLS`, subject to every RLS policy below). Neither
  migration sets a password; that is an out-of-band, per-environment step —
  see this ticket's "Phase 0 — shipped" section in
  `docs/ITINERARY-AND-READER-PRODUCTS-PLAN.md` for the exact rollout
  checklist, including what changes in deploy `.env` and in which order.
  **Production is not touched by shipping these migrations alone**: the app
  still connects as the historical superuser until that separate cutover
  step runs, and a superuser bypasses RLS and every grant unconditionally,
  so nothing below changes behaviour until then.
- **RLS (`FORCE ROW LEVEL SECURITY`) sits on**: `partnerships`, `campaigns`,
  `placements`, `offers`, `offer_places`, `voucher_claims`, `offer_events`,
  `offer_audit`, `print_plans`, `print_orders`, `print_order_items`,
  `print_subscriptions`, `shipments`, `payment_events` — every table this
  ticket's brief named plus every table one join away from a `site_id`
  column, filtered by `engine.current_site_id()`, which reads a session GUC
  (`SET LOCAL app.site_id = '<uuid>'`, set by the application per request/
  transaction) and fails closed (NULL, not an error, not "every row") on
  anything unset or unparseable. See migration 0017's docstring for the
  full per-table reasoning and `tests/test_rls_site_isolation.py` for the
  proof against a real connection.
- **Deliberately not yet covered**: `ad_events` and `partnership_audit` are
  exactly as site-scoped (via `campaign_id`/`partnership_id`) as the tables
  above but sit outside this ticket's explicit brief — a fast-follow, not
  an oversight; do not treat a clean run of `test_rls_site_isolation.py` as
  proof they are protected. `partner_users`/`partner_user_tokens` (0015)
  get an `org_id`-scoped policy when P8.1 (the partner portal) defines the
  session/`aud` model that policy needs to reason about — writing one now
  would be guessing. Reader-owned tables (`itineraries`, `destinations`,
  `reading_progress`, `saved_items`, `newsletter_subscribers`) are scoped by
  `identity_id`, not `site_id`, and are out of F6's stated scope.
- **A new ledger-shaped table added after 0016** inherits `now_runtime`'s
  standard `SELECT, INSERT, UPDATE, DELETE` by default (0016's `ALTER
  DEFAULT PRIVILEGES`) and must have its grant narrowed to `SELECT, INSERT`
  by hand in its own migration if it is meant to be append-only — the
  default does not know which new tables are ledgers.
- **Cross-site admin reads fan out at the application layer**, the same way
  ARCHITECTURE.md §2 already describes cross-city reads working: loop the
  known sites, `SET LOCAL app.site_id` to each in turn, merge the results.
  No grant or policy in this package lets one query see two sites' rows.

## Notes for later waves

- When a Payload instance for `now_platform.public` is built, moving
  `sites`/`orgs`/`campaigns`/`placements` there (if that's still the plan)
  is a migration that does `ALTER TABLE engine.x SET SCHEMA public`, run
  once `public` exists, plus updating every consumer's assumed schema.
  Until then, treat `now_platform.engine` as authoritative for all of it.
  Note this also means re-pointing `now_migrator`'s ownership and
  `now_runtime`'s grants at whatever role ends up running that Payload
  instance's own migrations.
