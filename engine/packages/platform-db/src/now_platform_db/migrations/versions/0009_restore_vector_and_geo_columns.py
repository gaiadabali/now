"""restore the vector and geo columns revision 0001 creates

Revision ID: 0009
Revises: 0008
Create Date: 2026-09-16

Repairs a platform database that was STAMPED rather than migrated.

`engine.alembic_version` on production reads 0005, so Alembic believes
revisions 0001-0005 have run. They have not, at least not all of them:
`engine.terms` has no `embedding` and no `geo`, and `engine.user_profiles`
has no `taste_vec_long` and no `taste_vec_short`, though revision 0001
creates all four along with three indexes over them. The same four are
missing from the local development copy, so this is not a production
accident — it is how that database was first assembled, from a dump or a
hand-run subset, with the version table set afterwards.

The drift gate never saw it. It builds its comparison by migrating an empty
database, so it checks that the migrations agree with the baseline and never
that any real database agrees with either. This migration is what closes
that, because from here a real database converges on the same schema as a
fresh one.

WHY A NEW REVISION AND NOT A FIX TO 0001.
0001 is correct; editing it would change history under every database that
genuinely ran it and still leave the stamped one untouched, because Alembic
would not re-run a revision it believes is applied. A forward repair runs
everywhere and is a no-op where the objects already exist.

EVERY STATEMENT IS IDEMPOTENT. `ADD COLUMN IF NOT EXISTS` and
`CREATE INDEX IF NOT EXISTS` mean this costs a database that already has
them nothing at all, which is the case for anything migrated from empty.

The columns are nullable with no default and nothing backfills them: they
hold embeddings that a separate job computes (ARCHITECTURE.md §4). Adding
them is a metadata-only change on a populated table, and the indexes are
partial on IS NOT NULL, so on a table whose column is entirely NULL they
build empty and instantly.

There is no downgrade. Dropping these would destroy embeddings that are
expensive to recompute, and the situation this repairs -- a column that
should exist and does not -- is not one anybody wants to return to.
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0009"
down_revision: Union[str, None] = "0008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- the extensions, FIRST -------------------------------------------
    # The stamped database has neither. `pg_extension` on it lists nothing
    # but plpgsql, which is why the columns below are missing rather than
    # merely different: `vector` and `geography` were not types that
    # database knew, so 0001's CREATE TABLE could never have run there.
    #
    # This is the part that is not cosmetic. Without `vector` the platform
    # cannot hold a term embedding at all, so the cold-start taste vectors
    # in ARCHITECTURE.md §4 have nowhere to live, and without `postgis`
    # there is no geo on a term. The drift gate reported it as two changed
    # tables; the cause was two absent extensions.
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")

    # --- engine.terms -----------------------------------------------------
    # Dimensions and types copied from 0001 verbatim; a vector column whose
    # dimension disagrees with the model that writes it fails at INSERT, not
    # here, which is a long way from the cause.
    op.execute("ALTER TABLE engine.terms ADD COLUMN IF NOT EXISTS geo geography(Point, 4326)")
    op.execute("ALTER TABLE engine.terms ADD COLUMN IF NOT EXISTS embedding vector(1536)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_terms_geo ON engine.terms USING gist (geo)")
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_terms_embedding_hnsw ON engine.terms "
        "USING hnsw (embedding vector_cosine_ops) WHERE embedding IS NOT NULL"
    )

    # --- engine.user_profiles --------------------------------------------
    op.execute(
        "ALTER TABLE engine.user_profiles ADD COLUMN IF NOT EXISTS taste_vec_long vector(1536)"
    )
    op.execute(
        "ALTER TABLE engine.user_profiles ADD COLUMN IF NOT EXISTS taste_vec_short vector(1536)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_user_profiles_taste_long_hnsw ON engine.user_profiles "
        "USING hnsw (taste_vec_long vector_cosine_ops) WHERE taste_vec_long IS NOT NULL"
    )


def downgrade() -> None:
    raise NotImplementedError(
        "0009 is a forward repair for a stamped database. Dropping these columns "
        "would destroy embeddings that cost money and time to recompute."
    )
