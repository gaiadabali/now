"""add `query` column to engine.interactions -- resolves open contract decision C1

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-08

Context (PROGRESS.md "Open contract decisions", C1): the frozen `interactions`
contract shipped by 0001 has no place for search-query text. The beacon
client (E0.4) currently smuggles it through `entity_type='search_query'`,
`entity_id=<query text>` -- which breaks the moment `entity_id` is read as
the uuid it is actually typed as. Site-search queries are the highest-intent
signal in the product and feed the E2.7 search eval set, so this needs a
real, typed column rather than continuing to overload `entity_id`.

This migration is additive-only: one nullable column on an existing table.
`query` is NULL for every non-search interaction. `entity_id` is untouched --
the E0.5 endpoint (`POST /v1/{site}/events`) special-cases
`kind='search'`/`entity_type='search_query'` on write and copies the beacon's
`entity_id` text into this column instead of trying to cast it as a uuid; see
`app/domain/events/normalize.py` for that logic.

`interactions` is `PARTITION BY RANGE (ts)` (declared partitioning, per
0001). `ALTER TABLE ... ADD COLUMN` on a partitioned parent in Postgres 11+
recurses to every existing partition automatically and is a metadata-only
change for a nullable column with no default -- no table rewrite, safe to
run against a city DB that already has live beacon traffic.
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[Sequence[str], str, None] = None
depends_on: Union[Sequence[str], str, None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE engine.interactions ADD COLUMN query text NULL")


def downgrade() -> None:
    op.execute("ALTER TABLE engine.interactions DROP COLUMN query")
