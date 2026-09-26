"""newsletter consent, lists, and the identity link

Revision ID: 0011
Revises: 0010
Create Date: 2026-09-26

Phase 0 (P0.1), plan §6.1. Repairs and extends 0006's `newsletter_subscribers`
per the owner's §11a answer 2: the *Newsletter* is the standard email
subscription with promotions opt-in **inside** it, not a separate
membership product — one row, one set of consent columns, no second table.

## Why `promo_consent_at` is separate from `status`

0006 already made the point that `status` must never default to
`'confirmed'` without an evidenced double opt-in. The same reasoning
applies one level down: a subscriber can be `confirmed` for the weekly and
still have never agreed to promotions. Indonesia's PDP Law (UU 27/2022)
wants consent that is explicit, "clearly distinguishable from other
matters", and provable on demand — a single boolean bundled into `status`
could not carry the "when, from where, what was ticked" evidence a
regulator or a subject-access request can ask for, and it could not express
"editorial yes, promotions no", which the plan makes the load-bearing
distinction between the two email products.

`promo_consent_at` is set **at confirmation, not at submit** (§6.1's
"Confirm" flow) — the column being nullable and separately timestamped is
what makes that timing distinction expressible; a boolean flipped at submit
time could not later prove which instant governs.

## Why `lists` is `text[]`, not a join table

Three values (`weekly | events | offers`) that grow slowly, read on every
send and every dashboard render, never queried by "which subscribers are
on list X" at a scale where a normalized join table would pay for its own
join — the newsletter's own subscriber count is in the thousands, not
millions, and the read path is always "this one subscriber's lists", never
a cross-subscriber list scan. `text[]` matches Postgres precedent already
in this schema (`itineraries.labels`, once 0013 lands; `weekdays smallint[]`
on the offers table 0012 lands first).

## Consent evidence columns are minimal and hashed on purpose

`consent_ip_hash` — not the raw IP. 0006 already declined to store IP/UA
for the base signup ("there is no purpose for them that justifies holding
them"); a promotions consent record is the one place an evidentiary trail
is actually required by law, so this migration adds the narrowest version
of it: a hash, not a searchable, re-identifiable raw address. Same shape as
the beacon's own consent-adjacent hashing convention.

## `manage_token_hash` is a second bearer credential, hashed like the first

`identity_tokens` (0007) already established the rule for this schema:
"a mailbox is not a safe place" — a bearer link is stored as a hash, never
in the clear, so a database dump is not a set of live unsubscribe/manage
links. This is a second, independent token store rather than a reuse of
`identity_tokens`, because a newsletter row is not always linked to an
`identities` row (`identity_id` here is nullable — a subscriber who never
creates a reader account still needs to manage their subscription by
token) and `identity_tokens.identity_id` is `NOT NULL`.

## Backfill

Every existing row (there are none in any environment this migration has
been run against, per the Phase 0 restart brief, but the statement is
written to be correct against a populated table regardless) gets
`lists = '{weekly}'` — the only list that existed before this migration,
since promotions/events sends have never gone out (F135, PROGRESS.md).
`promo_consent_at` stays NULL for every pre-existing row: there is no
evidence any of them opted into promotions, and manufacturing a consent
timestamp for a row that predates the promotions column would be exactly
the "opt-out consent" UU 27/2022 forbids.
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "0011"
down_revision: Union[str, None] = "0010"
branch_labels: Union[Sequence[str], str, None] = None
depends_on: Union[Sequence[str], str, None] = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE engine.newsletter_subscribers
            ADD COLUMN IF NOT EXISTS identity_id          uuid
                REFERENCES engine.identities(id) ON DELETE SET NULL,
            ADD COLUMN IF NOT EXISTS lists                text[] NOT NULL DEFAULT '{weekly}',
            ADD COLUMN IF NOT EXISTS promo_consent_at      timestamptz,
            ADD COLUMN IF NOT EXISTS promo_consent_source  text,
            ADD COLUMN IF NOT EXISTS consent_ip_hash       text,
            ADD COLUMN IF NOT EXISTS consent_user_agent    text,
            ADD COLUMN IF NOT EXISTS manage_token_hash     text
        """
    )
    # Explicit backfill even though the default already covers new rows —
    # any row inserted between 0006 and this migration reaching this line
    # without the column existing gets the same treatment as a brand new one.
    op.execute(
        """
        UPDATE engine.newsletter_subscribers
           SET lists = '{weekly}'
         WHERE lists IS NULL
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS newsletter_subscribers_manage_token_uq
            ON engine.newsletter_subscribers (manage_token_hash)
            WHERE manage_token_hash IS NOT NULL
        """
    )
    # "Promotions are only ever sent to rows with promo_consent_at set" (§6.1)
    # is a query that runs on every promotions send; the confirmed+consented
    # pair is the actual send-list filter, so it is composite and partial.
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS newsletter_subscribers_promo_consented_ix
            ON engine.newsletter_subscribers (site_slug)
            WHERE status = 'confirmed' AND promo_consent_at IS NOT NULL
        """
    )
    # The dashboard's "same row for a verified signed-in reader" read (§6.1,
    # P4.3): find this identity's subscription per masthead.
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS newsletter_subscribers_identity_ix
            ON engine.newsletter_subscribers (identity_id)
            WHERE identity_id IS NOT NULL
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS engine.newsletter_subscribers_identity_ix")
    op.execute("DROP INDEX IF EXISTS engine.newsletter_subscribers_promo_consented_ix")
    op.execute("DROP INDEX IF EXISTS engine.newsletter_subscribers_manage_token_uq")
    op.execute(
        """
        ALTER TABLE engine.newsletter_subscribers
            DROP COLUMN IF EXISTS identity_id,
            DROP COLUMN IF EXISTS lists,
            DROP COLUMN IF EXISTS promo_consent_at,
            DROP COLUMN IF EXISTS promo_consent_source,
            DROP COLUMN IF EXISTS consent_ip_hash,
            DROP COLUMN IF EXISTS consent_user_agent,
            DROP COLUMN IF EXISTS manage_token_hash
        """
    )
