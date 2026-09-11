# now-db

Alembic-owned `engine` schema, applied **identically** to every city
database (`now_jakarta`, `now_bali`, `now_test`, ...). This package is the
entire migration runner described in ARCHITECTURE.md §2 "Migration
discipline" — `site:create`, `site:migrate`, and the CI schema-hash gate all
live here.

Ownership rule: humans write `public` (Payload), machines write `engine`
(this package). Zero DDL exists anywhere outside
`src/now_db/migrations/versions/`.

## Install (dev)

```bash
pip install -e engine/packages/platform-db -e engine/packages/db
```

(`now-db` depends on `now-platform-db` because `site:create` writes the
platform `sites` registry row.)

## Connection env vars

| Var | Default | Used for |
|---|---|---|
| `NOW_PG_HOST` | `localhost` | host for every city + the `postgres` maintenance DB |
| `NOW_PG_PORT` | `5432` | port |
| `NOW_PG_USER` | `now` | role used for `CREATE DATABASE`, `CREATE EXTENSION`, migrations |
| `NOW_PG_PASSWORD` | `now` | password |
| `NOW_CITY_DATABASE_URL` | — | full DSN override for `now-db migrate --url` invocations from Alembic directly |

Defaults (`now`/`now`) intentionally match `engine-api`'s runtime
`city_db_user`/`city_db_password` defaults (`engine/apps/api/app/config.py`)
and the `POSTGRES_USER`/`POSTGRES_PASSWORD` the infra compose stack's
Postgres image bootstraps as its superuser (`engine/infra/postgres/init/`)
— this wave runs one Postgres role for everything (provisioning,
migrating, and request-serving). That role can currently do more than a
request-serving role strictly needs (`CREATE DATABASE`, `CREATE EXTENSION`)
purely because no split exists yet — see "Notes for later waves" below.
Override `NOW_PG_USER`/`NOW_PG_PASSWORD` independently of `engine-api`'s
own env vars once a dedicated migrator role exists.

`sites.db_ref` is stored as a **bare database name** (e.g. `now_bandung`),
matching `engine-api`'s `build_city_dsn()` — both sides build the full DSN
from the same host/port/user/password convention, so the API never needs a
code change to reach a database this package creates.

## CLI

```bash
now-db create <slug> --hostname <host> --name <name> [--locale en] [--timezone Asia/Jakarta] [--currency IDR] [--module <name>]...
now-db migrate --all                 # every registered, non-disabled city
now-db migrate --url <dsn-or-dbname> # exactly one
now-db hash --url <dsn-or-dbname> [--write-baseline]
now-db check --url <dsn-or-dbname>   # exit 1 on drift from schema_baseline.json
now-db check-term-refs --url <dsn-or-dbname> [--platform-url <dsn>]  # F92, see below
now-db ensure-partitions --url <dsn-or-dbname> [--days-ahead 7]
now-db drop-old-partitions --url <dsn-or-dbname> --retention-days <n>
```

`scripts/site-create.sh` / `.ps1` and `scripts/site-migrate.sh` / `.ps1` at
the repo root are thin wrappers around `create` / `migrate`.

Every command is idempotent: `create` on an already-provisioned slug
converges (database, migrations, registry row, scaffold dirs — none of it
errors on a second run); `migrate --all` running twice applies no new DDL
the second time.

## Testing without the infra stack

This package does not depend on `engine/infra/` or the top-level compose
file. `docker/Dockerfile.pg-test` builds a throwaway Postgres 16 +
pgvector + PostGIS image (`pgvector/pgvector:pg16` base + `postgresql-16-postgis-3`
from the same PGDG apt repo) for local development and CI
(`.github/workflows/schema-gate.yml` builds it fresh every run — no
registry dependency).

```bash
docker build -t now-pg-test:pg16 -f engine/packages/db/docker/Dockerfile.pg-test engine/packages/db/docker
docker run -d --name now-pg -e POSTGRES_PASSWORD=postgres -p 55432:5432 now-pg-test:pg16
```

## F92 — vocabulary referential-integrity check (`now-db check-term-refs`)

`now_platform.engine.terms` is the shared vocabulary (ARCHITECTURE.md §2). Several
tables in a city database carry one of its `id` values as a plain, unconstrained
uuid/text column, because **Postgres cannot declare an FK across databases**. Nothing
in the schema stops a term being deleted from the platform vocabulary while a city
still references it — E2.0c's `rawamangun` removal was harmless only because every one
of these tables happened to be empty at the time.

This is a **detection** guard, not a hot-path constraint: a trigger here would need a
live, transactional cross-database connection on every write to one of these tables,
which Postgres does not support. Matches the precedent ARCHITECTURE §8.G / PROGRESS.md
F82 already established for this exact cross-database limitation elsewhere (the
`abroad` term-uuid set is "resolved application-side once ... small, stable,
cacheable" rather than joined in SQL) — resolved app-side, same as everywhere else this
limitation comes up in this codebase.

`now_db.term_refs.find_orphaned_term_refs()` enumerates every known city-side source of
a platform term uuid — found by grepping every writer of one, not assumed from a single
table name:

| Source | Live? | Why |
|---|---|---|
| `engine.entity_terms.term_id` | yes | a currently-active tag on a real article/place |
| `engine.embeddings.entity_id` (`entity_type='term'`) | yes | E2.4's per-term embedding cache — pruning is deliberately disabled for `entity_type='term'` (`now_embeddings/cli.py`), so a stale row here is never cleaned up on its own |
| `public.classification_reviews.term_id` | **no** (historical) | Payload's review-queue snapshot of an AI proposal's *original* term id (F86/E2.8) — a term retired after a review was already decided is expected, not a corruption, so it is reported but never fails the check on its own |

A source table that does not exist in a given city (e.g. `now_test` has no Payload
`public` schema at all) is skipped for that database, checked via
`information_schema.tables` up front so a missing table never leaves a connection's
transaction aborted mid-sweep.

Wired in two places, both exercising the same `now_db.term_refs` module:

1. **`now-db check-term-refs --url <city>`** — standalone, `exit 1` if any **live**
   orphan is found (a historical-only finding still prints but exits 0). For CI or an
   ops on-demand check, mirroring the existing `now-db check` schema-drift gate's
   exit-code convention.
2. **`now-db migrate` / `migrate --all`** — runs the same check after migrating and
   prints a loud, **non-fatal** summary. Deliberately non-fatal: a pre-existing
   data-integrity issue in unrelated rows must not block an otherwise-successful
   migration run from completing — a different kind of urgency than `now-db check`'s
   hard schema-hash gate, which protects DDL identity and genuinely should block a
   deploy.

**Why `migrate`/CI, not a scheduled sweep:** `site:migrate --all` is the command this
repo already runs on every deploy and the one operators already watch the output of —
"wired where it will actually be seen" (this ticket's own words) means the path already
proven to get attention, not a new cron job nobody configured yet. `now-db
check-term-refs` additionally exists standalone so CI (`schema-gate.yml`'s
`vocabulary-integrity-selftest` job) and ad-hoc ops checks don't have to run a full
migration just to ask the question.

**This was not hypothetical during development.** A real, pre-existing orphan was
found live in `now_jakarta.engine.embeddings` while this check was being built:
`entity_id=58e339f8-2f72-422b-8ac1-af3c95ce16c1`, `entity_type='term'`, written
2026-09-08 by E2.4's original backfill — almost certainly the `rawamangun` leftover
(F89). `now-db check-term-refs --url now_jakarta` correctly reported it (exit 1);
`now_bali` (which started at zero embeddings) had none. It was removed as an explicit,
reported cleanup (not a side effect of testing) once the guard proved it could detect
it: `engine.embeddings` `entity_type='term'` row count in `now_jakarta` went
408 → 407, now matching `now_platform.engine.terms` exactly; `check-term-refs` then
reports clean (exit 0).

**Deletion is not made safe by this ticket.** Detection is the requirement this ticket
set; making a term deletion in `now_platform` automatically safe (e.g. a cross-database
`ON DELETE` cascade-equivalent) is a bigger behavioural change to how the vocabulary is
managed — not proposed here to avoid silently changing that behavior. The one-off
cleanup above was a manual `DELETE` against a confirmed orphan, not a new automated
deletion path.

## Rollout notes

- The baseline migration (`0001`) is additive-only against an empty
  database — there is no live data to protect on a brand-new city. Its
  `downgrade()` drops every table it created; do not run it against a city
  with real interactions/impressions data without a backup.
- `interactions` / `impressions` are RANGE-partitioned by day.
  `ensure_daily_partitions` is called automatically at the end of
  `site:create`/`site:migrate` (so a brand-new city can accept beacon
  traffic immediately) and is also exposed as `now-db ensure-partitions`
  for a scheduled job. **Wiring an actual cron/systemd-timer entry is an
  infra decision, out of this package's scope** — this package only
  guarantees the operation is safe to run daily, and safe to run twice.
- `now-db drop-old-partitions --retention-days <n>` exists but is not
  scheduled by this package either, and has no default retention policy —
  that is a product/legal decision (how long is raw behavioural data kept),
  not an engineering one.

## Notes for later waves

- **§8.G partial indexes on `(site_id, type, status)` and GiST on `geo`**
  apply to `public.articles` / `public.places`, which are Payload-owned and
  do not exist until E1.6 ships. Add them in a migration that lands
  alongside or after E1.6 — not here. (This package's GiST/HNSW indexes on
  `engine` tables — `embeddings.vec`, and `terms.geo` / `terms.embedding`
  over in `now-platform-db` — are already in place.)
- **E1.4 (taxonomy seed)**: extend `now_db.provisioning.seed_city`, don't
  add a second seeding entry point. It currently only verifies
  `engine.type_relations` was populated by the baseline migration.
- **Role/grant split**: this wave uses one Postgres role for everything
  (provisioning, migration, and — via `engine-api`'s defaults — runtime
  queries). Before commerce data lands in `now_platform.engine.ad_events`
  (E4), consider a dedicated read/write runtime role with `UPDATE`/`DELETE`
  revoked on append-only ledger tables, granted only `INSERT`+`SELECT`.
  Not implemented in E0.2 — flagging so it isn't forgotten, not because it
  blocks this wave.
- **Migration 0002+**: this migration set is single-threaded across the
  whole project (see PROGRESS.md's ownership map) — coordinate before
  adding a revision.
