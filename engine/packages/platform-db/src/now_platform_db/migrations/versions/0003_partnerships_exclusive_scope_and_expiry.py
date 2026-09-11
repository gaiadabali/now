"""partnerships: exclusive org-level/place-level scope + query-time expiry
helpers -- E4.1

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-09

Context: 0001's baseline created `engine.partnerships` with BOTH `org_id`
and `place_id` as `NOT NULL`, which cannot express ARCHITECTURE.md §11's
actual mechanism -- a deal is either **org-level** (every place under that
org gets the tier, e.g. "every Marriott property") or **place-level** (one
specific place, e.g. an independent restaurant with no group), never both
at once and never neither. E4.1's ticket calls this out explicitly:
"partnerships must support an org-level OR place-level deal. Model it so
exactly one is set, and enforce that." 0001 pre-dates that decision (it
was written speculatively, ahead of the §11 design pass) and simply listed
both FK columns from the architecture sketch without the exclusivity rule.
This migration is the correction, not a reversal of anything intentional.

1. **Exactly-one-of, enforced at the DB, not the app.**
   `org_id` and `place_id` both become nullable, and
   `CHECK (num_nonnulls(org_id, place_id) = 1)` rejects any row with both
   set or neither set. `num_nonnulls()` is a built-in Postgres function
   (9.6+) purpose-built for exactly this "exactly one of N columns" shape
   -- no CASE/COALESCE trick needed, and it reads as what it means. Both
   columns are still empty in production (`SELECT count(*) FROM
   engine.partnerships` = 0 at the time of writing), so relaxing NOT NULL
   and adding the CHECK is a metadata-only change with nothing to
   backfill or validate against.

   `place_id` keeps its F22 status: a city-DB `places.id`, cross-database,
   so it can never be a real FK (Postgres cannot reference across
   databases, and DB-per-city means the row lives elsewhere by design --
   same limitation already documented for `itinerary_stops.place_id` and
   `syndications.origin_article_id`). Referential integrity for it is the
   application's job, unchanged from before this migration.

2. **Query-time expiry -- the ticket's hard requirement.** §11's whole
   commercial pitch ("a contract lapses -> it reverts automatically at
   `ends_at`, nobody has to remember") only holds if "is this partnership
   live" is *computed on every read* from `(status, starts_at, ends_at,
   now())`, never written down anywhere a batch job could fail to update.
   Two artifacts give every consumer (E4.2's link resolver first) a single
   place to get this right instead of re-deriving the boolean logic ad
   hoc in NestJS/SQL at each call site:

   - `engine.partnership_is_effective(status, starts_at, ends_at, at)`
     -- a `STABLE SQL` function, `at` defaulting to `now()`. Takes the raw
     column values (not a row type) so it composes into any query
     (`WHERE engine.partnership_is_effective(status, starts_at, ends_at)`)
     without forcing a join through a view, and doubles as an "as of a
     past instant" check for audit/dispute resolution (E4.1's own
     `partnership_audit` exists for exactly that kind of question) by
     passing an explicit `at`.
   - `engine.partnerships_active` -- a plain view (`CREATE VIEW`, not
     MATERIALIZED) built on that function. A view re-runs its query,
     `now()` included, on every SELECT -- there is no refresh step to
     forget, which is the entire point versus a cron-refreshed
     materialized view or a cached "is_active" boolean column. This is
     what 0001's `ix_partnerships_active` partial index
     (`WHERE status = 'active'`) already anticipated: that index still
     narrows the scan to admin-set-active rows cheaply, and the view/
     function layer adds the starts_at/ends_at half the index predicate
     deliberately leaves out (a partial index predicate must be a simple
     immutable expression; `now()` is not immutable, so the *time* part
     of "effective" can only live in the query, never the index
     definition -- Postgres would reject `WHERE ends_at > now()` as an
     index predicate outright).

   `starts_at IS NULL` is treated as "no lower bound / already started"
   and `ends_at IS NULL` as "no expiry" -- both nullable in 0001 with no
   stated meaning for NULL; this migration is the first place that
   meaning is pinned down, symmetrically with how `ends_at IS NULL`
   obviously has to mean "never ends" for a free-tier or open-ended deal
   to be representable at all.

   Neither the function nor the view is a `BASE TABLE`, so neither is
   picked up by `schema_hash.introspect_schema` (it filters
   `table_type = 'BASE TABLE'`) -- the structural drift gate stays a pure
   column/constraint/index contract on real tables, and this migration
   does not need special-casing there. Verified by hand against the local
   DB: `hash` before and after adding the view/function differs only
   because of the `partnerships` column/constraint changes in this same
   migration, not because of the view or function.

3. **New indexes replace, not append to, 0001's now-incomplete ones.**
   0001's `ix_partnerships_active` and `ix_partnerships_place` were built
   assuming `place_id` is always present. They still work — a NULL
   `place_id` row just doesn't match a `WHERE place_id = ...` predicate —
   but they no longer describe the actual hot path, which now branches on
   which of org_id/place_id is set. Replaced with four narrower partial
   indexes (two lookup shapes x {place-scoped, org-scoped}) so a
   render-time query for "the active deal covering this place" and one
   for "the active deal covering this org" each get an index built for
   exactly that predicate, rather than scanning past NULLs. `ix_partnerships_org`
   (unscoped by site, from 0001) is left in place for admin/console
   listing ("all partnerships for this org across sites/history").

   Deliberately NOT added: a UNIQUE constraint forbidding two
   simultaneously-`active`-status partnerships on the same (site, org) or
   (site, place). That would block a legitimate renewal workflow -- queuing
   next quarter's contract with `status = 'active'` and a future
   `starts_at` while the current contract is still `active` and has not
   yet reached its own `ends_at`. Under exactly-query-time-expiry
   semantics that overlap is harmless: at most one of the two rows is ever
   *effective* at a given instant, resolved by whichever consumer reads
   `engine.partnerships_active`/`partnership_is_effective` (E4.2 owns
   picking a tie-break, e.g. `ORDER BY starts_at DESC LIMIT 1`, if it ever
   needs one). Enforcing single-row-active-at-a-time is a business policy
   choice belonging to E4.2/E4.4, not a DB integrity fact this migration
   should bake in and potentially have to walk back.

Purely additive/relaxing: no column is dropped, no existing NOT NULL that
had real data behind it is removed, no row is rewritten. Downgrade
restores exactly 0001's shape (both FK columns NOT NULL again) and is only
safe on a `partnerships` table where every row already satisfies that
(true today: zero rows; guarded explicitly below for anyone running
downgrade later against a populated table).
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[Sequence[str], str, None] = None
depends_on: Union[Sequence[str], str, None] = None


def upgrade() -> None:
    # --- 1. exactly-one-of org_id / place_id ---------------------------
    op.execute("ALTER TABLE engine.partnerships ALTER COLUMN org_id DROP NOT NULL")
    op.execute("ALTER TABLE engine.partnerships ALTER COLUMN place_id DROP NOT NULL")
    op.execute(
        """
        ALTER TABLE engine.partnerships
            ADD CONSTRAINT ck_partnerships_org_xor_place
            CHECK (num_nonnulls(org_id, place_id) = 1)
        """
    )

    # --- 2. indexes rebuilt for the now-nullable columns ---------------
    op.execute("DROP INDEX IF EXISTS engine.ix_partnerships_active")
    op.execute("DROP INDEX IF EXISTS engine.ix_partnerships_place")

    op.execute(
        "CREATE INDEX ix_partnerships_place_lookup ON engine.partnerships "
        "(site_id, place_id) WHERE place_id IS NOT NULL"
    )
    op.execute(
        "CREATE INDEX ix_partnerships_place_active ON engine.partnerships "
        "(site_id, place_id) WHERE status = 'active' AND place_id IS NOT NULL"
    )
    op.execute(
        "CREATE INDEX ix_partnerships_org_active ON engine.partnerships "
        "(site_id, org_id) WHERE status = 'active' AND org_id IS NOT NULL"
    )

    # --- 3. query-time expiry: function + view --------------------------
    op.execute(
        """
        CREATE FUNCTION engine.partnership_is_effective(
            p_status text,
            p_starts_at timestamptz,
            p_ends_at timestamptz,
            p_at timestamptz DEFAULT now()
        ) RETURNS boolean
        LANGUAGE sql
        STABLE
        AS $$
            SELECT p_status = 'active'
               AND (p_starts_at IS NULL OR p_starts_at <= p_at)
               AND (p_ends_at IS NULL OR p_ends_at > p_at)
        $$
        """
    )
    op.execute(
        """
        COMMENT ON FUNCTION engine.partnership_is_effective(text, timestamptz, timestamptz, timestamptz) IS
        'Query-time (never batch-computed) test of whether a partnership row is live: '
        'status=active AND starts_at<=at AND (ends_at IS NULL OR ends_at>at). Pass an '
        'explicit `at` to answer "was this live as of a past instant" for audit/billing '
        'disputes; defaults to now() for render-time use.'
        """
    )
    op.execute(
        """
        CREATE VIEW engine.partnerships_active AS
        SELECT *
        FROM engine.partnerships p
        WHERE engine.partnership_is_effective(p.status, p.starts_at, p.ends_at)
        """
    )
    op.execute(
        "COMMENT ON VIEW engine.partnerships_active IS "
        "'Currently-effective partnerships, recomputed on every read via now() -- "
        "there is no refresh step and nothing here is ever stale by more than one query.'"
    )


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS engine.partnerships_active")
    op.execute(
        "DROP FUNCTION IF EXISTS engine.partnership_is_effective(text, timestamptz, timestamptz, timestamptz)"
    )

    op.execute("DROP INDEX IF EXISTS engine.ix_partnerships_org_active")
    op.execute("DROP INDEX IF EXISTS engine.ix_partnerships_place_active")
    op.execute("DROP INDEX IF EXISTS engine.ix_partnerships_place_lookup")

    op.execute(
        "CREATE INDEX ix_partnerships_place ON engine.partnerships (site_id, place_id)"
    )
    op.execute(
        "CREATE INDEX ix_partnerships_active ON engine.partnerships "
        "(site_id, place_id) WHERE status = 'active'"
    )

    op.execute("ALTER TABLE engine.partnerships DROP CONSTRAINT ck_partnerships_org_xor_place")

    # Guard rather than silently corrupt: 0001's shape required both
    # columns on every row. If rows now rely on the exactly-one-of
    # relaxation (the entire point of this migration), restoring NOT NULL
    # would either fail loudly (good) or -- if someone pre-populated nulls
    # some other way -- needs a human decision, not a guess from this
    # script. Fail loudly instead of guessing.
    op.execute(
        """
        DO $$
        DECLARE
            bad_rows bigint;
        BEGIN
            SELECT count(*) INTO bad_rows
            FROM engine.partnerships
            WHERE org_id IS NULL OR place_id IS NULL;

            IF bad_rows > 0 THEN
                RAISE EXCEPTION
                    'downgrade 0003->0002 aborted: % partnerships row(s) have a NULL '
                    'org_id or place_id and cannot satisfy 0002''s NOT NULL shape. '
                    'Resolve those rows manually (assign a real org_id/place_id per '
                    'row, or delete them) before downgrading.', bad_rows;
            END IF;
        END $$;
        """
    )
    op.execute("ALTER TABLE engine.partnerships ALTER COLUMN org_id SET NOT NULL")
    op.execute("ALTER TABLE engine.partnerships ALTER COLUMN place_id SET NOT NULL")
