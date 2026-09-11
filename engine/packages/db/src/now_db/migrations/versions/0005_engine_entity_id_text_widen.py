"""widen remaining `engine.*` entity-reference columns to `text` (F33)

Revision ID: 0005
Revises: 0004
Create Date: 2026-09-08

Closes PROGRESS.md follow-up F33, the same class of bug as C4 (interactions)
and 0004 (embeddings): four more `engine.*` columns were typed `uuid NOT
NULL` under the assumption that every embeddable/scoreable entity has a uuid
primary key. `public.articles.id` and `public.places.id` are Payload integer
serials -- there is no uuid to reference.

    column                      | before        | after
    -----------------------------|---------------|------
    quality_scores.entity_id     | uuid NOT NULL | text NOT NULL
    entity_terms.entity_id       | uuid NOT NULL | text NOT NULL
    covisitation.entity_a        | uuid NOT NULL | text NOT NULL
    covisitation.entity_b        | uuid NOT NULL | text NOT NULL
    rail_cache.article_id        | uuid NOT NULL | text NOT NULL

`entity_terms.term_id` is untouched -- it references
`now_platform.engine.terms.id`, a real uuid PK, so it is typed correctly
already. Same reasoning as 0004's table distinguishing article/place (no
uuid) from term (real uuid).

`travel_matrix.place_a`/`place_b` have the identical bug (they reference
`public.places.id`, also a Payload integer serial) but are explicitly OUT OF
SCOPE for this migration -- not part of the F33 brief, which names only the
four columns above. Flagged in the F33 completion report as still
inconsistent with the `text` convention; left for whoever next touches
`travel_matrix` (no current writer -- E?  travel-time backfill hasn't
shipped) to fix in its own migration, in this same shape.

## Why this migration is safe to run as-is against a populated table

Unlike 0004 (which changed `vec`'s pgvector *dimension* -- a genuinely
destructive operation with no lossless cast between 1536-dim and 384-dim
vectors, hence that migration's populated-table guard), `uuid -> text` is a
lossless, information-preserving widening for every existing row: every
valid uuid has an exact, unambiguous text representation, and
`USING <col>::text` cannot fail or truncate. No guard is needed and none is
added -- this migration runs unconditionally, upgrade or downgrade
direction, on empty or populated tables alike, AT THE COLUMN-TYPE LEVEL.

## What this migration does NOT fix, and deliberately leaves alone

`now_jakarta.engine.quality_scores` currently holds 4,772 rows written by
E2.6's `uuid5(entity_type, id)` stopgap
(`now_quality/entity_id.py`, deleted by this same F33 task in the `quality`
package). Those rows' `entity_id` values are hashes of the form
`0000a5a1-7a61-5521-a0e4-50914f6dfaea` -- valid uuids, and this migration's
`::text` cast preserves them faithfully as e.g. `"0000a5a1-...5d9b10"`. But
a hash is not the same value as the native integer PK it was derived from,
so after this migration alone those rows are STILL unjoinable to
`public.articles.id` -- widening the column type does not retroactively fix
data written under the old convention.

That data-level fix -- `DELETE FROM engine.quality_scores WHERE
entity_type = 'article'` followed by a `now-quality score` rerun once the
uuid5 stopgap is deleted -- is a data migration performed by hand as a
separate, explicit step (see the F33 completion report), NOT embedded in
this schema migration. Folding a DELETE into DDL would make this migration
non-reversible in the ordinary "downgrade restores prior state" sense and
would silently discard the 4,772 rows for any city that runs this migration
before its own quality-package rescore -- a decision that belongs to the
operator running the rollout, not to an unconditional migration step.

`entity_terms`, `covisitation`, `rail_cache` are confirmed EMPTY (0 rows) in
all three city DBs (`now_jakarta`, `now_bali`, `now_test`) as of this
migration -- verified directly, not assumed (see the F33 report for the
query output) -- so the type change itself carries no data-loss risk for
those three tables in this environment.

## Downgrade

`text -> uuid` is only lossless if every existing value happens to already
be valid uuid syntax. Immediately after `upgrade()` with no intervening
writes, that is trivially true (the values were uuids seconds ago). It is
NOT true once `quality_scores` is re-keyed to hold native integer PKs as
text (e.g. `"4821"`) -- the entire point of F33 -- or once any other
consumer starts writing genuine integer-PK-derived text values into these
columns. Matching 0003's precedent: `downgrade()` does not attempt to
paper over that by inventing a synthetic uuid for a non-uuid string; it
reissues the type change as-is and lets Postgres raise a clear
`22P02 invalid_text_representation` error if the live data no longer
supports it. Downgrading after real integer-keyed data has landed requires
a deliberate data decision (truncate, or derive a fresh uuid5 mapping) that
this migration will not make silently.
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[Sequence[str], str, None] = None
depends_on: Union[Sequence[str], str, None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE engine.quality_scores ALTER COLUMN entity_id TYPE text USING entity_id::text")
    op.execute("ALTER TABLE engine.entity_terms ALTER COLUMN entity_id TYPE text USING entity_id::text")
    op.execute("ALTER TABLE engine.covisitation ALTER COLUMN entity_a TYPE text USING entity_a::text")
    op.execute("ALTER TABLE engine.covisitation ALTER COLUMN entity_b TYPE text USING entity_b::text")
    op.execute("ALTER TABLE engine.rail_cache ALTER COLUMN article_id TYPE text USING article_id::text")


def downgrade() -> None:
    # See "Downgrade" note above -- these will raise 22P02 rather than
    # silently fabricating data if any column holds a non-uuid text value
    # (e.g. a native integer PK stored as text, which is exactly what F33
    # exists to make happen).
    op.execute("ALTER TABLE engine.rail_cache ALTER COLUMN article_id TYPE uuid USING article_id::uuid")
    op.execute("ALTER TABLE engine.covisitation ALTER COLUMN entity_b TYPE uuid USING entity_b::uuid")
    op.execute("ALTER TABLE engine.covisitation ALTER COLUMN entity_a TYPE uuid USING entity_a::uuid")
    op.execute("ALTER TABLE engine.entity_terms ALTER COLUMN entity_id TYPE uuid USING entity_id::uuid")
    op.execute("ALTER TABLE engine.quality_scores ALTER COLUMN entity_id TYPE uuid USING entity_id::uuid")
