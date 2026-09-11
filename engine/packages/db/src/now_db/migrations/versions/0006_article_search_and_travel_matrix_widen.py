"""engine.article_search (F41) + widen engine.travel_matrix place columns to text (F44)

Revision ID: 0006
Revises: 0005
Create Date: 2026-09-09

Two independent, unrelated changes bundled into one migration slot because
Alembic is single-threaded this wave (PROGRESS.md Wave 7) and F44 is
explicitly "free" only while `travel_matrix` is still empty.

## Part 1 — `engine.article_search` (F41)

Materialises the lexical-search tsvector that E3.1's `now-search` package
had to approximate on the fly in `pg_temp` (measured 2,619 ms/query for a
literal per-query jsonb walk; the `pg_temp` memoization got that down to
2-6ms/query but paid a ~4s per-*connection* warm-up and, more importantly,
used a simplified SQL body-text extractor that skips `list`, `gallery` and
`columns` blocks entirely — see F40). This table is refreshed by a Python
worker using `now_content_clean.metrics.visible_text_out`, the same
lxml-based block-walker `now-embeddings` already uses for the semantic
side, which handles every block type correctly. See
`engine/packages/search/README.md` for the worker/backfill writeup — this
migration only creates the empty, indexed table.

    CREATE TABLE engine.article_search (
        entity_id      integer PRIMARY KEY,
        tsv            tsvector NOT NULL,
        body_text_hash text NOT NULL,
        updated_at     timestamptz NOT NULL DEFAULT now()
    );
    CREATE INDEX ix_article_search_tsv ON engine.article_search USING gin(tsv);

### Why NO foreign key to `public.articles(id)`, despite the task brief's sketch

The brief's sketch DDL includes `REFERENCES public.articles(id) ON DELETE
CASCADE` and asks this migration to verify the FK is actually legal before
keeping it. It is not — verified two independent ways, not assumed:

1. **`now_test` has no `public.articles` table at all.** `now_test` is the
   synthetic third tenant (ARCHITECTURE.md E0.6 / §3.5's tenancy-enforcement
   test bed) and carries only `engine` + PostGIS's `spatial_ref_sys` in
   `public` — verified directly (`\\dt public.*` against the live `now_test`
   database lists exactly one table, not `articles`). A `REFERENCES
   public.articles(id)` clause in this migration would make `upgrade()`
   fail outright on `now_test` with `relation "public.articles" does not
   exist` — not a theoretical ordering risk, an immediate hard failure on
   one of the three databases this migration must apply to cleanly.

2. **Payload's own migrations `DROP TABLE "articles" CASCADE`.** Payload
   (`engine/packages/cms/src/migrations/20260908_131927_initial_schema.ts`,
   the `down()` function) tears down and rebuilds `public` with
   `DROP TABLE "articles" CASCADE` — Payload-owned, not something this
   package can change per ARCHITECTURE.md §1's schema-ownership rule. A
   cross-schema FK from `engine.article_search` would make that CASCADE
   silently drop the FK constraint (data survives, but referential
   integrity silently vanishes and is never automatically restored when
   `public.articles` is recreated on the next `up()`) — the exact
   "Payload's own migrations dropping/recreating the table" ordering
   problem the task brief flagged as a reason to drop the FK.

Migration 0001's own baseline already establishes this precedent
explicitly for every other `engine.*` table that logically references
`public.articles`/`public.places` (`embeddings`, `entity_terms`,
`quality_scores`, `covisitation`, `rail_cache`, `travel_matrix` — see
0001's docstring: "No foreign keys are declared against `public` ...
Referential integrity for these columns is enforced by the API/worker
layer, not the database."). `article_search` follows the same rule for the
same reason: `entity_id integer PRIMARY KEY` with no FK, referential
integrity enforced by the tsv worker (which only ever upserts a row after
confirming the article exists and is published) and by `delete_stale`
sweeping rows for articles no longer in `public.articles` at all.

`entity_id` is a plain `integer` (not `text`, unlike F33/0005's
`entity_id` columns) because this table is article-only by construction —
there is no `entity_type` discriminator and therefore no need for the
`text`-to-hold-either-an-integer-or-a-uuid trick 0004/0005 exist for.
`public.articles.id` is itself a native Payload integer serial (verified:
`\\d public.articles` on `now_jakarta`), so `integer` is the correct,
non-lying type for this column from day one.

## Part 2 — `engine.travel_matrix.place_a`/`place_b`: uuid -> text (F44)

Same class of bug as F33 (0005), same fix shape, deliberately left out of
0005's scope at the time (0005's docstring calls this out by name as
"OUT OF SCOPE for this migration ... left for whoever next touches
`travel_matrix`"). `place_a`/`place_b` reference `public.places.id`, a
Payload integer serial — there is no uuid to hold.

**Verified empty before widening, not assumed**: `SELECT count(*) FROM
engine.travel_matrix` returns `0` on all three of `now_jakarta`,
`now_bali`, `now_test` as of this migration (no travel-time backfill has
run — ARCHITECTURE.md's E5 itinerary engine, the first consumer, has not
shipped). `uuid -> text` is lossless regardless (every valid uuid has an
exact text representation), matching 0005's reasoning, but the empty-table
fact is what makes this genuinely free today per F44's PROGRESS.md entry —
after a travel-time backfill lands this same widening would require
rewriting every row's `place_a`/`place_b` values from a fabricated uuid
back to the native integer id it was always describing, not just a type
tag change.

## Downgrade

`article_search`: plain `DROP TABLE`, no populated-table guard needed —
this migration also creates the table, so there is never live data to
protect on the way down within one migrate-up/migrate-down cycle. (A
downgrade run *after* the tsv worker has populated real rows will discard
them — this is a materialized-cache table, trivially rebuilt by
`now-search backfill-tsv`, not a system of record, so that is an
acceptable, documented trade-off, not an oversight.)

`travel_matrix`: reissues the type change in reverse, matching 0005's
precedent exactly — `text -> uuid` only succeeds if every existing value
happens to already be valid uuid syntax, which is trivially true on an
empty table (or one still holding only the uuids this table shipped with)
and will raise a clear `22P02` if a real integer-keyed travel-time backfill
has since written non-uuid text. No synthetic uuid is fabricated to paper
over that.
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[Sequence[str], str, None] = None
depends_on: Union[Sequence[str], str, None] = None


def upgrade() -> None:
    # --- Part 1: engine.article_search (F41) ---------------------------
    op.execute(
        """
        CREATE TABLE engine.article_search (
            entity_id      integer NOT NULL,
            tsv            tsvector NOT NULL,
            body_text_hash text NOT NULL,
            updated_at     timestamptz NOT NULL DEFAULT now(),
            PRIMARY KEY (entity_id)
        )
        """
    )
    # No FK to public.articles(id) -- see docstring "Why NO foreign key".
    op.execute("CREATE INDEX ix_article_search_tsv ON engine.article_search USING gin(tsv)")

    # --- Part 2: engine.travel_matrix widen (F44) -----------------------
    op.execute("ALTER TABLE engine.travel_matrix ALTER COLUMN place_a TYPE text USING place_a::text")
    op.execute("ALTER TABLE engine.travel_matrix ALTER COLUMN place_b TYPE text USING place_b::text")


def downgrade() -> None:
    # Reverse Part 2 first (independent of Part 1, order doesn't matter,
    # but reversing in mirror order of upgrade() matches this package's
    # existing style).
    op.execute("ALTER TABLE engine.travel_matrix ALTER COLUMN place_b TYPE uuid USING place_b::uuid")
    op.execute("ALTER TABLE engine.travel_matrix ALTER COLUMN place_a TYPE uuid USING place_a::uuid")

    op.execute("DROP INDEX IF EXISTS engine.ix_article_search_tsv")
    op.execute("DROP TABLE IF EXISTS engine.article_search")
