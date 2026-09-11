"""orgs: candidate-roster provenance columns -- E4.1 (partner_roster load)

Revision ID: 0004
Revises: 0003
Create Date: 2026-09-09

Context: E4.1 loads `jakarta/content/extracted/partner_roster.jsonl` --
1,562 candidate orgs mined from outbound-link clusters across the archive
(E1.5's follow-on), each carrying a `confidence` (0.35-0.9), a
`type_guess`, per-domain `rel` counts, first/last-seen dates, and free-text
`notes` explaining *why* the loader believes what it believes (a
synthesized-parent inference, a brand-keyword-in-domain guess, etc). 60 of
those are wholly synthesized group parents that never appear as a direct
outbound link themselves (the `intercontinental` apex, inferred solely
from `bali.intercontinental.com` / `jakartapondokindah.intercontinental.com`
being its children -- exactly the case the ticket names) and 44 more are
brand-keyword guesses explicitly capped at confidence 0.6 by the
extractor. The ticket's language ("177 low-confidence... ~117 brand-keyword")
is an approximation from an earlier pass; the actual file measured at load
time has 104 rows at confidence <= 0.6 (60 at 0.35 + 44 at 0.6) -- see the
loader's own report for the real, queried number. Reported here rather
than silently reconciled to the ticket's figure.

0001's `orgs` table has nowhere to put any of this -- it models a
*confirmed* org (name, slug, website, booking_url, type) for a partner
that has actually signed something. E4.1's brief is explicit: "keep the
confidence and provenance so a human can review -- do not silently promote
guesses to facts." Two things follow from that:

1. This migration adds columns for the *candidate* facts (confidence,
   provenance, the extractor's classification guess) as a layer separate
   from the *confirmed* facts already on the table -- never overwrites or
   repurposes an existing column.

2. `orgs.type` (existing, confirmed-fact column) is deliberately left
   untouched by the loader that uses this migration's new columns -- the
   extractor's guess lands in the new `type_guess` column instead, and
   nothing in this ticket's scope promotes `type_guess` -> `type`
   automatically. Only a human (via a later console/admin action, E4.4)
   or an explicit follow-up migration/script should ever copy one into
   the other, and only after `review_status` says so.

New columns:
    type_guess     text          -- extractor's classification guess (free/eat/do/
                                     stay/drink/null); NEVER copied into `type`
                                     by any loader -- that copy is a human decision.
    confidence     numeric(3,2)  -- 0.00-1.00, extractor's confidence in this org
                                     candidate existing/being correctly clustered.
    review_status  text          -- 'pending' | 'confirmed' | 'rejected'. Defaults
                                     to 'pending' for every row this loader writes,
                                     confidence notwithstanding -- see above, nothing
                                     is auto-confirmed regardless of how high its
                                     confidence is.
    synthesized    boolean       -- true for a group parent that was inferred from
                                     its children's subdomains rather than observed
                                     as a direct link itself (the `intercontinental`
                                     case).
    domains        text[]        -- every domain the extractor clustered under this
                                     org; `website` (confirmed-fact column) is set by
                                     the loader from domains[0] when non-empty, but
                                     the full list stays here for a reviewer to check
                                     that choice.
    link_count     integer       -- outbound-link occurrences across the archive.
    article_count  integer       -- distinct articles carrying at least one such link.
    first_seen     date          -- earliest article publish date carrying the link.
    last_seen      date          -- latest.
    rel_audit      jsonb         -- {"none": n, "nofollow": n, "sponsored": n} --
                                     ties straight back to E1.5's 9,135/9,128 finding,
                                     per-org.
    notes          text[]        -- extractor's free-text reasoning for this row
                                     (e.g. why a parent was synthesized, or why a
                                     brand-keyword parent guess needs manual check).
    source         text          -- provenance tag for the load batch, e.g.
                                     'partner_roster:jakarta:2026-09-09'; lets a
                                     later re-extraction be told apart from this one.

All nullable (or defaulted) and additive; `orgs` has 0 rows in production
at the time of writing, so there is nothing to backfill and no rewrite
risk either way, but the columns are written to tolerate rows that predate
this migration (a manually-created confirmed org with no candidate
provenance at all) just as well as roster-loaded ones.

`confidence`'s CHECK is deliberately loose (`0 <= confidence <= 1`, not
tied to the specific 0.35/0.6/0.7/0.85/0.9 values seen in today's roster)
-- those are the current extractor's output levels, not a fixed vocabulary
this schema should freeze in place the way F20 warns against for Payload
taxonomy ENUMs. Same reasoning applies to `review_status`: a CHECK against
a fixed 3-value list rather than a real Postgres ENUM, so adding a fourth
workflow state later (e.g. 'needs_more_data') is one migration touching
one CHECK constraint, not an ENUM ALTER plus a CMS restart.
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[Sequence[str], str, None] = None
depends_on: Union[Sequence[str], str, None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE engine.orgs ADD COLUMN type_guess text")
    op.execute(
        "ALTER TABLE engine.orgs ADD COLUMN confidence numeric(3,2) "
        "CHECK (confidence >= 0 AND confidence <= 1)"
    )
    op.execute(
        "ALTER TABLE engine.orgs ADD COLUMN review_status text NOT NULL DEFAULT 'pending' "
        "CHECK (review_status IN ('pending', 'confirmed', 'rejected'))"
    )
    op.execute("ALTER TABLE engine.orgs ADD COLUMN synthesized boolean NOT NULL DEFAULT false")
    op.execute("ALTER TABLE engine.orgs ADD COLUMN domains text[] NOT NULL DEFAULT '{}'::text[]")
    op.execute("ALTER TABLE engine.orgs ADD COLUMN link_count integer")
    op.execute("ALTER TABLE engine.orgs ADD COLUMN article_count integer")
    op.execute("ALTER TABLE engine.orgs ADD COLUMN first_seen date")
    op.execute("ALTER TABLE engine.orgs ADD COLUMN last_seen date")
    op.execute("ALTER TABLE engine.orgs ADD COLUMN rel_audit jsonb")
    op.execute("ALTER TABLE engine.orgs ADD COLUMN notes text[] NOT NULL DEFAULT '{}'::text[]")
    op.execute("ALTER TABLE engine.orgs ADD COLUMN source text")

    # Review-queue lookup: "show me everything still pending" and "show me
    # the low-confidence ones first" are the two access patterns a human
    # reviewer actually needs; both are cheap with a partial index instead
    # of scanning all 1,562+ rows every time the console opens the queue.
    op.execute(
        "CREATE INDEX ix_orgs_review_status_pending ON engine.orgs (confidence) "
        "WHERE review_status = 'pending'"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS engine.ix_orgs_review_status_pending")
    op.execute("ALTER TABLE engine.orgs DROP COLUMN source")
    op.execute("ALTER TABLE engine.orgs DROP COLUMN notes")
    op.execute("ALTER TABLE engine.orgs DROP COLUMN rel_audit")
    op.execute("ALTER TABLE engine.orgs DROP COLUMN last_seen")
    op.execute("ALTER TABLE engine.orgs DROP COLUMN first_seen")
    op.execute("ALTER TABLE engine.orgs DROP COLUMN article_count")
    op.execute("ALTER TABLE engine.orgs DROP COLUMN link_count")
    op.execute("ALTER TABLE engine.orgs DROP COLUMN domains")
    op.execute("ALTER TABLE engine.orgs DROP COLUMN synthesized")
    op.execute("ALTER TABLE engine.orgs DROP COLUMN review_status")
    op.execute("ALTER TABLE engine.orgs DROP COLUMN confidence")
    op.execute("ALTER TABLE engine.orgs DROP COLUMN type_guess")
