"""fix `engine.embeddings` for a real embedding run (E2.4)

Revision ID: 0004
Revises: 0003
Create Date: 2026-09-08

Two independent problems, found while building the E2.4 embeddings pipeline,
fixed together because both block inserting a single real row:

1. `entity_id` was typed `uuid NOT NULL` (0001), which silently assumed
   every embeddable entity has a uuid primary key. False for the two
   entity_types this migration exists to unblock: `public.articles.id`
   and `public.places.id` are Payload integer auto-increment PKs, not
   uuids. This is the *same class of bug* PROGRESS.md's C4 already found
   and fixed for `engine.interactions.entity_id` -- and the fix is the
   same shape: widen to `text`, do not paper over it with a derived
   `uuid5` hash (C4 explicitly rejected that pattern for `interactions`
   because hashing destroys the original identifier; the same objection
   applies here -- a hash of an integer PK you can already reference
   directly buys nothing and makes every join require re-deriving or
   storing the hash both ways).

     entity_type | entity_id source                        | example
     ------------|------------------------------------------|----------
     article     | public.articles.id (Payload integer PK)   | "4821"
     place       | public.places.id (Payload integer PK)     | "203"
     term        | now_platform.engine.terms.id (real uuid)  | "3fa8...-..."

   `text` holds all three without lying about any of them.

2. `vec` was `vector(1536)` -- an OpenAI-family dimension assumed at
   baseline time before any provider was chosen. E2.4's investigation
   (see `engine/packages/embeddings/README.md`) found no API key
   available: Ollama Cloud's OpenAI-compatible endpoint (the one
   configured provider) has no `/v1/embeddings` route at all -- verified
   by a direct call, not inferred -- so the only real provider is local
   (`BAAI/bge-small-en-v1.5` via `fastembed`/ONNX, CPU, no key, no network
   dependency after the one-time model download), which is 384-dimensional.
   Padding a 384-dim vector to 1536 with zeros, or truncating a
   hypothetical 1536-dim vector to 384, would both corrupt cosine
   similarity (padding changes every dot product's denominator
   asymmetrically; truncation discards the second half of the learned
   semantic space) -- neither is a defensible substitute for "the column
   matches the model that actually produced the numbers in it." The
   column changes instead.

   `dim` is added as an explicit, redundant-with-`vector_dims(vec)` integer
   column (enforced equal by a CHECK) so a future reader never has to
   introspect pgvector internals to know a row's dimensionality, and so
   that IF a later wave adds a second model at a *different* dimension
   (e.g. a real OpenAI-family key eventually shows up), the schema
   decision is visible in the data from day one rather than requiring
   another archaeology pass. That said: pgvector requires one fixed
   dimension per column, so a second concurrent model at a different
   dimension is NOT representable in this same `vec` column -- it would
   need a sibling column (`vec_1536 vector(1536)`) or a second table, a
   decision deliberately deferred to whoever adds that model, because
   guessing its dimension now would be speculative DDL. `model` (already
   part of the primary key) plus `dim` together make that future migration
   a data-driven decision, not an archaeology one -- the stated goal of
   this task.

   `text_hash` is added so re-embedding is a no-op query against unchanged
   text rather than a full model pass -- E2.1 will fill `primary_type`/
   `format`/facets and every article must be re-embedded once it does (the
   E2.4 task brief is explicit that this is not a one-shot job).

This migration intentionally refuses to run against a populated table (see
the guard in `upgrade()`) -- it is a **pre-data** schema correction, safe
today because no city DB has ever had a row in `engine.embeddings` (E2.4
has not run before this migration). It is not a general-purpose "resize
the vector column" migration; if this ever needs to run against live
embeddings, that is a real re-embedding data migration, not a metadata
change, and this code will refuse rather than silently destroying vectors.
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[Sequence[str], str, None] = None
depends_on: Union[Sequence[str], str, None] = None

EMBEDDING_DIM = 384  # BAAI/bge-small-en-v1.5 -- see docstring above


def upgrade() -> None:
    conn = op.get_bind()
    existing = conn.execute(sa.text("SELECT count(*) FROM engine.embeddings")).scalar_one()
    if existing:
        raise RuntimeError(
            f"engine.embeddings already has {existing} row(s) -- this migration drops "
            "and recreates `vec` (a destructive operation for existing vectors) and is "
            "only safe against an empty table. If this fires, E2.4 has already been run "
            "against this database ahead of this migration, which should not happen "
            "given the task's dependency order. Resolve by hand: this needs a real "
            "re-embedding data migration, not a metadata-only schema change."
        )

    # The HNSW index depends on `vec`; drop it explicitly before the column
    # swap for clarity (dropping the column would take the index with it
    # implicitly, but doing it by name documents intent and matches this
    # package's existing style in 0001/0003).
    op.execute("DROP INDEX IF EXISTS engine.ix_embeddings_hnsw")

    # (1) entity_id: uuid -> text. USING-cast is harmless on an empty table;
    # written generically (not "TRUNCATE then retype") so this migration
    # stays correct if the guard above is ever loosened deliberately.
    op.execute("ALTER TABLE engine.embeddings ALTER COLUMN entity_id TYPE text USING entity_id::text")

    # (2) vec: 1536 -> 384. No lossless ALTER COLUMN ... TYPE exists between
    # two different pgvector dimensions (they are genuinely different
    # types), so this drops and re-adds rather than attempting a cast that
    # Postgres would reject anyway.
    op.execute("ALTER TABLE engine.embeddings DROP COLUMN vec")
    op.execute(f"ALTER TABLE engine.embeddings ADD COLUMN vec vector({EMBEDDING_DIM}) NOT NULL")

    # (3) dim: explicit, checked against the vector's own reported length so
    # the two can never silently disagree.
    op.execute("ALTER TABLE engine.embeddings ADD COLUMN dim integer NOT NULL")
    op.execute(
        "ALTER TABLE engine.embeddings ADD CONSTRAINT ck_embeddings_dim_matches_vec "
        "CHECK (dim = vector_dims(vec))"
    )

    # (4) text_hash: sha256 hex digest (64 chars) of the exact string that
    # was embedded. Drives idempotent, resumable re-embedding -- the worker
    # compares this before calling the model at all.
    op.execute("ALTER TABLE engine.embeddings ADD COLUMN text_hash text NOT NULL")

    op.execute(
        f"CREATE INDEX ix_embeddings_hnsw ON engine.embeddings "
        f"USING hnsw (vec vector_cosine_ops)"
    )


def downgrade() -> None:
    conn = op.get_bind()
    existing = conn.execute(sa.text("SELECT count(*) FROM engine.embeddings")).scalar_one()
    if existing:
        raise RuntimeError(
            f"engine.embeddings has {existing} row(s) written under the 384-dim/text "
            "contract -- downgrading to the 1536-dim/uuid contract would destroy them "
            "(a 384-dim vector cannot become a 1536-dim one by any cast, and a Payload "
            "integer id like \"4821\" cannot become a uuid). Truncate the table by hand "
            "first if you really mean to discard every embedding."
        )
    op.execute("DROP INDEX IF EXISTS engine.ix_embeddings_hnsw")
    op.execute("ALTER TABLE engine.embeddings DROP CONSTRAINT IF EXISTS ck_embeddings_dim_matches_vec")
    op.execute("ALTER TABLE engine.embeddings DROP COLUMN IF EXISTS text_hash")
    op.execute("ALTER TABLE engine.embeddings DROP COLUMN IF EXISTS dim")
    op.execute("ALTER TABLE engine.embeddings DROP COLUMN vec")
    op.execute("ALTER TABLE engine.embeddings ADD COLUMN vec vector(1536) NOT NULL")
    op.execute("ALTER TABLE engine.embeddings ALTER COLUMN entity_id TYPE uuid USING entity_id::uuid")
    op.execute(
        "CREATE INDEX ix_embeddings_hnsw ON engine.embeddings "
        "USING hnsw (vec vector_cosine_ops)"
    )
