# `@now-engine/cms`

ONE Payload 3 config, instantiated per city (ARCHITECTURE.md §3.5). `cms-jakarta` and
`cms-bali` are the same Docker image running the same code — the only thing that differs
between two running instances is the `DATABASE_URI` env var. This package owns `public`
in each city database and must never create, alter or read anything in `engine` —
Alembic owns `engine` and never touches `public`. See ARCHITECTURE.md §1 principle 2.

## Quick start

```bash
cp .env.example .env
# edit .env: DATABASE_URI, SITE_SLUG, PLATFORM_DATABASE_URI, REDIS_URL
npm install
npx payload migrate      # applies src/migrations/* to whatever DATABASE_URI points at
npm run dev              # next dev — admin panel at http://localhost:3000/admin
```

To point the exact same checkout at a different city, change only `DATABASE_URI` (and
`SITE_SLUG`, which is cosmetic — admin-panel labelling and log lines only, never branching
logic) and re-run `npx payload migrate` / restart. No code changes, no rebuild.

## Facet vocabulary across two databases

ARCHITECTURE.md §4/§5: the seeded taxonomy (type, subtype, location, format, cuisine,
vibe, occasion, audience, amenities, price_band, topic — 268 terms, including the
`unknown` type sentinel added by F49) lives in
`now_platform.engine.terms` / `now_platform.engine.facets` (E1.4). Payload binds exactly
one database per instance — the city DB — so it cannot reach that table through its own
DB adapter.

**Chosen approach:** a short-lived, explicitly read-only `pg` connection to
`PLATFORM_DATABASE_URI`, opened once at CMS boot (module load, before `buildConfig`
runs — see `payload.config.ts`'s top-level `await loadVocabulary()` and
`src/lib/vocabulary.ts`), used only to `SELECT` term/facet rows and build the `select`
field `options` for Articles/Places. Payload then bakes those options into a real
Postgres `ENUM` type per facet (e.g. `enum_places_type`) via its own migration — so the
vocabulary constraint is enforced at the database level, not just in the admin UI. This
was verified directly: `payload.create()` with a free-typed, non-seeded `primaryType`
value is rejected by the underlying enum type (see `scripts/verify-vocabulary.mjs`).

**Why this over a synced read-only copy table in the city DB's own `public` schema** (the
alternative the ticket names):
- A synced copy needs a sync job (cron/worker) that is out of this package's scope
  (`E1.6` owns only `engine/packages/cms/**`) and introduces a second source of truth
  that can drift from `now_platform.engine.terms` between syncs.
- The vocabulary is small (268 terms) and changes rarely — a taxonomy edit, not a
  per-article edit — so "options are fixed for the process lifetime, refreshed on
  restart" is an acceptable trade-off for zero extra moving parts.
- It keeps the *write* path untouched: this module only ever `SELECT`s, from a database
  this package owns no part of either way.

**Honest limitation:** CMS boot needs network access to `now_platform` once, at startup.
If that database is unreachable, the CMS does not crash — `src/lib/vocabulary.ts` logs
loudly (`[cms] vocabulary unavailable...`) and boots with empty option lists rather than
refusing to start entirely (an editor should still be able to fix a title typo while the
platform DB has a blip). That is a real, visible degradation, not a silent one. Because
the options are baked into a Postgres enum by a **migration**, not fetched live per
request, adding a new seeded term requires: re-run `payload migrate:create` +
`payload migrate` on every city DB, then restart every `cms-<city>` process — this is a
real operational cost, tracked as a follow-up rather than solved here (see "Notes for
E1.8" below).

## `articles.body_blocks`: a `json` field, not rich text

Deliberately a `json` field (`src/fields/bodyBlocks.ts`), which the Postgres adapter maps
straight to a `jsonb` column — exactly the type ARCHITECTURE.md §5 specifies. E1.2's
cleaner already emits a stable, versioned block-array shape (heading / paragraph / image
/ gallery / list / quote / embed / separator / columns / raw_html) verified over all
4,772 articles at ~0% content loss; re-modelling that as Payload's Lexical rich-text AST
would need a lossy two-way converter and make E1.8's loader output unusable without one.

Verified with a REAL E1.2 output, not a hand-built fixture: `test/fixtures/body-blocks.sample.json`
is the literal `now-content-clean` output for archive article wp_id 121 (18 blocks, 5
distinct types including `embed` and `separator`). `scripts/verify-body-blocks-roundtrip.mjs`
creates an article with it via Payload's local API, reads it back, and asserts every
field of every block is unchanged. One nuance surfaced by that script and worth knowing
for E1.8: Postgres `jsonb` (unlike `json`) normalizes object key order on storage, so
`JSON.stringify(before) !== JSON.stringify(after)` even though the data is bit-for-bit
identical field-by-field — this is inherent to `jsonb` everywhere (and is the type
ARCHITECTURE.md itself specifies), not something Payload does. Nothing should ever read
`body_blocks` by raw string/byte comparison; read named fields.

## `places.geo`: a real ARCHITECTURE.md/Payload friction point

ARCHITECTURE.md §5 types `places.geo` as `geography(Point,4326)` so `engine-api` can run
PostGIS `ST_DWithin` radius queries (§7 Row 2 "Nearby", §15). **Payload has no `geography`
field type** — its own `point` field maps to Postgres's *native* `point` type, which
`ST_DWithin`/geography functions cannot consume. Discovering this by using Payload's
`point` field and only noticing at the SQL level would have quietly broken Row 2 ranking
after this ticket was marked done.

Resolution, reported rather than silently worked around:
- Editors edit plain `lat`/`lng` number fields (`src/collections/Places.ts`) — simple,
  obviously correct UI, no dependency on a `geography` type existing in Payload's field
  system.
- A **hand-authored, Payload-owned migration** (`src/migrations/20260908_140000_places_geography.ts`)
  adds a real `geography(Point,4326)` column plus a `BEFORE INSERT OR UPDATE` trigger
  that derives it from `lat`/`lng` on every write, so the two can never drift.
- This is still 100% within the schema-ownership rule: Alembic is not involved anywhere
  in that file. It is Payload's own migration runner (`payload migrate`) shaping a table
  Payload itself created in the previous migration — exactly analogous to what Alembic
  does inside `engine`, just on the other side of the boundary.
- Verified for real: `scripts/verify-places-geo.mjs` creates a place via Payload's API
  with lat/lng, then queries the SAME connection pool Payload uses
  (`payload.db.pool.query(...)`) with a genuine `ST_DWithin` call and gets `true` for a
  point 130m away and would get `false` outside the radius — this is not a documentation
  claim, it is a passing PostGIS query against Payload-written data.

## Adding a value to a seeded enum: two migrations, not one (F49)

F20 already flagged that a new seeded `type`/`subtype`/... term needs a Payload
migration plus a restart of every `cms-<city>` (the vocabulary is baked into a real
Postgres `ENUM` at migration time, not read live). F49 (adding the `unknown` sentinel
type) hit the concrete version of that friction: **`ALTER TYPE ... ADD VALUE` and then
using the new value cannot share a transaction.** Postgres allows the `ADD VALUE` itself
inside a transaction block (9.6+), but not a reference to that value — in a `WHERE`, a
`SET`, even an implicit cast — until the adding transaction has committed (error 55P04,
"unsafe use of new value of enum type"). `@payloadcms/drizzle`'s migration runner wraps
each migration *file's* `up()` in exactly one transaction (`initTransaction` /
`commitTransaction` in `migrate.js`), so a single migration that both added `'unknown'`
and `UPDATE`d rows to it would fail every time, not intermittently.

Fix, verified by actually hitting and then avoiding the error: split into two migration
files — `20260909_150000_add_unknown_type_enum_value.ts` (`ALTER TYPE ... ADD VALUE IF
NOT EXISTS`, only ever adds, never uses, the four enums the shared `type` facet backs:
`enum_places_type`, `enum__places_v_version_type`, `enum_articles_primary_type`,
`enum__articles_v_version_primary_type`) and
`20260909_150100_places_unknown_type_and_status_type_index.ts` (the data `UPDATE` plus
the F51 index), which runs in the *next* migration file and therefore the next,
separate transaction. Payload's `migrate:down` rolls back a whole batch in reverse
**name** order (`getMigrations` sorts `-batch, -name`), so as long as the two files sort
in the order they must undo in — data/index migration first, enum-add migration last —
`down()` never tries to strip a value a still-referencing row needs; down-tested for
real (`payload migrate:down` then `payload migrate` again against `now_jakarta`, table
contents and `pg_enum` diffed before/after both ways). Postgres has no `DROP VALUE`, so
that migration's `down()` recreates the enum (rename old → create new without the value
→ `ALTER COLUMN ... USING ... ::text::newtype` → drop old) rather than loosening the
column to `text`, which would remove the exact guard-rail (a typo'd type value rejected
at the database, not just the admin UI) this ENUM exists for.

## E2.8 — the classification review queue (`src/collections/ClassificationReviews.ts`)

ARCHITECTURE.md §6's confidence gate ("review: confidence < 0.85 -> human queue") is
the only thing that makes Hansel's "everything migrates and gets classified best-effort"
call safe — without a real review surface, that decision means writing unreviewed
guesses straight into `primary_type`/`type`, which §8.A's competitor exclusion then
treats as fact. `classification-reviews` is that surface: an editor-facing queue, sorted
confidence-ascending, with accept / correct / **unclassifiable** as three first-class
outcomes (never a forced choice between three wrong types).

**The `public`/`engine` schema-ownership split (§1 principle 2), resolved the way E1.6
resolved the equivalent problem for the facet vocabulary:** E2.1's confidence/provenance
model (`weight`, `source`, `confidence`) lives in `engine.entity_terms`, which this
package must never create, alter, or write to. Two decisions follow from that, both
different from the vocabulary case (which reads `engine`, read-only) because
`entity_terms` has nothing this queue actually needs:

- Reading `engine.entity_terms` directly turned out to be a dead end regardless of the
  ownership question — its real, migrated columns are only `entity_type, entity_id,
  term_id, weight, source, confidence, created_at` (verified against
  `engine/packages/db/src/now_db/migrations/versions/0001_baseline_engine_schema.py`,
  not just ARCHITECTURE.md's summary table). There is no reasoning/evidence column at
  all — "why the classifier chose it" has nowhere to live in `engine` today. So
  `classification-reviews` is a real `public` table (Payload owns every byte of it) that
  stores a durable **snapshot** of one proposal — including `reasoning`, which is new,
  not copied from anywhere.
- This package's own code (collections, hooks, `payload.config.ts`) never touches
  `engine.entity_terms`, in either direction. The queue is *populated* by whichever
  process computes a low-confidence proposal calling Payload's REST/Local API to create
  a row — the same "machine calls Payload" shape `publishArticleEvent.ts` uses in
  reverse (there Payload announces to a machine; here a machine writes to Payload). When
  an editor decides, `src/hooks/reviewQueueHooks.ts`'s `afterChange` hook (a) writes the
  final value onto the real `articles`/`places` row via Payload's own Local API — a
  table Payload already owns, no different from any other field edit — and (b)
  announces a `classification.reviewed` domain event over the existing Redis transport
  (`now:domain-events`, same channel+stream `publishArticleEvent.ts` uses), carrying
  `source: 'editor'` and the platform `term_id` for the FINAL value (plus
  `previous_term_id` when a correction changed the term, so the row keyed on the
  superseded term can be retired — `entity_terms`' primary key is
  `(entity_type, entity_id, term_id)`, so "eat" corrected to "drink" is a new key, not an
  update of the old one). Actually upserting `engine.entity_terms` with
  `source='editor'` is `engine-worker`'s job (out of this package's scope, and not built
  yet) — exactly principle 2's "machines write engine", never Payload.

**Proving a re-run cannot clobber an editor correction** (the property this ticket says
matters most) required standing in for that not-yet-built `engine-worker`, since nothing
consumes `classification.reviewed` today. `scripts/verify-review-no-clobber.mjs` does,
end to end, against real Postgres and real Redis:
1. Writes a real `engine.entity_terms` row directly via raw SQL (`source='ai'`) —
   simulating E2.1's classifier, the only "machine" ever meant to write there. This is
   the one place in this ticket's deliverables that touches `engine` directly, and it is
   a verification script standing in for code that does not exist yet, never this
   package's own runtime path.
2. Drives a real correction through Payload's actual Local API (the same code path the
   admin UI/REST API use) and confirms, from a real subscription opened *before* the
   correction, that `now:domain-events` actually delivers the event with the right
   `term_id`/`previous_term_id`/`source`.
3. Simulates `engine-worker` consuming that event: retires the superseded row, upserts
   the new one with `source='editor'`.
4. Simulates a classifier **re-run** attempting to overwrite it, using the
   source-respecting conditional upsert (`... WHERE entity_terms.source <> 'editor'`)
   that is the actual contract `engine-worker`'s real classifier-ingest path must
   implement — the same discipline PROGRESS.md F27 already established for
   `places.type` (the E1.8 loader's upsert omits protected columns from its `SET`).
   Asserts the row is untouched.
5. **Control case**: runs the identical upsert against an ordinary, never-reviewed
   `source='ai'` row and asserts it *does* get refreshed — proving the guard
   discriminates rather than being vacuously true.

Run it yourself: `npm run verify:review-no-clobber` (`npx payload run
scripts/verify-review-no-clobber.mjs`).

**F20 (vocabulary ENUM churn) and what this queue needs on restart:** `proposedValue`/
`finalValue` are deliberately plain `text`, NOT backed by a Postgres ENUM the way
Articles'/Places' own facet fields are — a single review row can propose into any of
four different term vocabularies (`type`/`subtype`/`format`/`location`) depending on
`facetKey`, and a Postgres column can only ever back one ENUM. Enforcement instead
happens in application code, checked against the same in-memory `vocabulary` map
Articles/Places already use (see the `validate` function in `ClassificationReviews.ts`).
Net effect: **this collection's own schema needs zero migration when the taxonomy
delta lands** — only a `cms-<city>` restart, identical to every other facet field, to
reload `vocabulary`. The eventual write-back onto `articles.primaryType`/`places.type`
etc. still goes through those collections' own ENUM-backed fields, so a proposal
correcting into a term that was seeded *after* the last restart is still rejected until
that restart happens — same F20 cost as today, not a new one.

**Scope, stated plainly:** only the four ARCHITECTURE.md §6 *classification* facets
(type, subtype, format, location) — not the seven *tagging* facets (cuisine, vibe,
occasion, audience, amenities, price_band, topic), which are a separate §6 pipeline
stage with its own confidence and were never this ticket's "classify... (WP category =
prior)" step.

## F86 — the no-clobber guarantee is enforced at the DB, not just by one query

`scripts/verify-review-no-clobber.mjs` (above) proves the intent end to end, but the
actual protection it demonstrates lives in the *shape of one SQL statement*
(`... WHERE source <> 'editor'`) inside a script standing in for `engine-worker`, which
does not exist yet. Nothing stopped a **different** writer — a re-run of E2.1's
classifier re-proposing the same (entity, facet) and updating the existing review row, a
backfill script, an ops fix-up — from issuing a plain `UPDATE` with no idea that clause
needs to exist, and silently clobbering a human's decision on `classification_reviews`
itself (QA.6 demonstrated exactly this shape of gap against the sibling
`engine.entity_terms` table).

Migration `20260910_060000_classification_reviews_no_clobber_trigger` adds a
`BEFORE UPDATE` trigger, `classification_reviews_no_clobber`, directly on
`public.classification_reviews`: once a row's `review_state` has left `'pending'` under
`source='editor'` (i.e. a human decided it — the exact condition `autoPopulateOnDecision`
establishes, and the only way `source` ever becomes `'editor'`), any further `UPDATE`
that does not *itself* assert `source='editor'` is rejected outright
(`RAISE EXCEPTION`, `ERRCODE = restrict_violation`) — the whole write, not just the
`source` column. `ON CONFLICT DO UPDATE` is caught too (it is still a row-level `UPDATE`
event under the hood); a raw `UPDATE` is caught the same way, whatever its `WHERE`
clause claims.

This is raw SQL (a `CREATE OR REPLACE FUNCTION` + `CREATE TRIGGER`), not anything
Payload's collection-config-derived schema tracks — **confirmed empirically, not
assumed**: running `payload migrate:create` immediately after this migration proposes
*zero* statements referencing the trigger or its function. The only thing it does
propose is the pre-existing, already-known F89 landmine (recreating
`enum_places_area_term`/`enum__places_v_version_area_term` without `'rawamangun'`,
because that term was retired from the platform vocabulary and Payload's own snapshot
still expects it) — unrelated to this migration, and, per F89's standing rule, must be
generated-and-deleted, never applied.

Verified against the real CMS path (`npm run verify:review-no-clobber-trigger` — see
`scripts/verify-classification-reviews-no-clobber-trigger.mjs`), not just reasoned about:
1. **Control** — an undecided (`source='ai'`, `review_state='pending'`) row is freely
   updatable by a raw writer (the guard is not vacuous).
2. **Legitimate CMS write** — an editor's decision, driven through Payload's real Local
   API (the same hooks the admin UI exercises), succeeds and stamps `source='editor'`.
3. **Attack** — a simulated automated writer (`source` stays `'ai'`, both a plain
   `UPDATE` and an `INSERT ... ON CONFLICT DO UPDATE` keyed on `id`) is rejected by the
   trigger; the row is confirmed byte-for-byte unchanged afterward.
4. **Legitimate second decision** — the same editor deciding again (through the real
   Local API) on the now-decided row still succeeds — the guard protects against
   automated writers, not against further human review.

Run against both `now_jakarta` and `now_bali` (`DATABASE_URI` override for the second),
migrated up/down/up to confirm the trigger+function round-trip byte-identically, and
re-run again once the table held thousands of real E2.1/E2.3-written rows (no longer
empty, per PROGRESS.md F91) to confirm nothing about the guard depends on the table
being otherwise quiet. Every fixture the verify script creates is deleted in a `finally`
— it never touches a real, pre-existing row.

Does **not** touch `engine.entity_terms` — that is a separate, Alembic-owned `now-db`
concern; see PROGRESS.md F92 for the analogous cross-database integrity gap there.

**Unvalidated against real classifier output.** E2.1 has not run — `select count(*)
from engine.entity_terms` is 0 and every real article has `primary_type IS NULL` in
every city DB as of this ticket (PROGRESS.md F50/F74, reconfirmed live before writing
this). `scripts/seed-review-queue.mjs` populates the queue with clearly-labelled
FABRICATED evidence over real, already-loaded articles/places so the UI/filtering/
sorting/workflow can be exercised at all — it is not a claim about what the real
classifier will say, and every reasoning string it writes says so.

**A pre-existing migration-tooling gap this ticket surfaced but did not cause or fix:**
running `payload migrate:create` for this collection also generated four spurious
`ALTER TYPE ... ADD VALUE 'unknown' BEFORE 'wellness'` statements against the
`primary_type`/`type` enums. Checked against the live database before deciding what to
do with them: those enums already contain `'unknown'` (F49, already applied) — drizzle's
own snapshot (`src/migrations/20260908_131927_initial_schema.json`) was just never
updated by F49's hand-authored raw-SQL migrations, so it still records the original
8-value enum. Running the generated statements as-is would have thrown
`42710: type already has value` against every already-migrated city DB. Removed from
`20260910_020207_add_classification_reviews.ts` (both `up()` and `down()`) with a
comment explaining why; the snapshot-drift itself is unrelated to E2.8 and left for
whoever next touches those enums.

## Places: plain versions, not drafts (a real Payload naming collision)

`src/collections/Places.ts` originally declared `versions: { drafts: {...} }` (mirroring
Articles). Running the ACTUAL migration generator (`payload migrate:create`) surfaced a
genuine bug rather than a hypothetical one: Payload's internal drafts column `_status`
and a user-defined field also named `status` (Places' active/closed/pending_review
lifecycle field) generate colliding Postgres enum type names, producing an invalid
migration where `status` defaulted to `'active'` against an enum containing only
`'draft'`/`'published'`. This was caught by reading the generated SQL, not assumed safe.
Fix: Places uses `versions: { maxPerDoc: 20 }` (version history, no drafts) — which is
also the semantically correct choice, since ARCHITECTURE.md doesn't describe an
editorial draft/publish workflow for places, only a lifecycle `status`.

## RBAC — editor / author / admin

`src/collections/Users.ts` defines the three roles. Authors can create and edit their own
drafts freely; only editor/admin may move a document into the published state. This is
enforced twice, deliberately: `access.update` at the collection level, and a second,
explicit `beforeChange` hook (`src/hooks/enforcePublishRole.ts`) specifically on the
draft→published transition, because Payload's `_status` field isn't a normal field
`access` can gate per-value. Verified as a REAL rejection, not a documented intention:
`scripts/verify-rbac-publish-gate.mjs` has an `author`-role local-API call to publish
throw, and the identical call as `editor` succeed.

## Publish hook → Redis

`src/hooks/publishArticleEvent.ts` (an `afterChange` hook on Articles) publishes to Redis
on every draft→published / published→draft / republish transition. Payload computes
nothing about the article itself — no embeddings, no facets, no tags — it only announces
enough identifying data (`entity_id`, `legacy_wp_id`, `primary_type`, `format`,
`series_key`) for `engine-worker` to go fetch the row and do the real work
(ARCHITECTURE.md: "Payload must not compute anything itself"). Publishes to both a
pub/sub channel (`now:domain-events`) and a Stream (`now:domain-events:stream`) so the
worker team can pick either consumption model without a change here. Verified with a real
message: `scripts/verify-publish-event.mjs` subscribes to the actual Redis channel
*before* publishing an article via Payload's local API and prints what Redis delivers.

## Zero site-name literals

`npm run lint:site-literals` (`scripts/lint-site-literals.mjs`) greps this package's
source for `'jakarta'`/`'bali'` and fails on a match, with two narrow, documented
exclusions: `src/migrations/**` (generated from the live seeded *location* taxonomy,
which legitimately contains terms named "jakarta"/"bali" as places — ARCHITECTURE.md §3.5
even documents Jakarta's own archive carrying "Bali Updates" articles) and
`test/fixtures/**` (a real archive article's prose, not code). This is a package-scoped
version of the repo-wide CI lint E0.6 owns; it can be lifted into that check wholesale.

## Editorial essentials checklist

- **Drafts + scheduled publish**: Articles use `versions.drafts.schedulePublish: true`
  (Payload's built-in `payload_jobs` queue handles the scheduled transition).
- **Versions**: both Articles (via drafts) and Places (via plain versioning) keep history.
- **Media with alt text**: `src/collections/Media.ts` — `alt` is required.
- **Roles**: see above.

## Known limitation of this verification pass

Everything above was verified through Payload's own `payload run <script>` local-API
runner (esbuild/tsx-based — Payload's documented way to run Local API scripts) against
**real** `now_jakarta` and `now_bali` databases, real `now_platform`, and real Redis.

`next build` / `next dev` (webpack-based) could **not** be run to completion in this
environment: webpack's own config-schema validation rejects any path containing `!`
(`configuration.context`, `output.path`, etc. — "reserved for loader syntax"), and this
repository's root directory is literally named `now!`. This reproduces with Turbopack
disabled *and* enabled (`@payloadcms/next`'s `withPayload` additionally refuses
Turbopack production builds below Next 16.1). This is an environment/path issue specific
to this checkout, not a defect in this package's collections, hooks, or config — but it
does mean the actual browser-rendered admin UI was not visually confirmed in this
session, only every database-facing behaviour it depends on. A container build (where
the workdir is `/app`, not the host checkout path) should not hit this, but that was not
verified here either — flagging honestly rather than claiming a green build that didn't
run.
