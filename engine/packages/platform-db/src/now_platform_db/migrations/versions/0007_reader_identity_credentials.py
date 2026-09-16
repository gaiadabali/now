"""reader identity credentials, tokens and saved items

Revision ID: 0007
Revises: 0006
Create Date: 2026-09-16

E8.1 — docs/READER-IDENTITY.md.

`identities` shipped in 0001 as `id · email · created_at · stated_prefs`.
That is a table describing a person, not one that can authenticate them:
no hash, no salt, no verification state, no lockout counters, no name.
`user_profiles` shipped beside it and has been empty ever since for the
same reason — nothing can write a `user_id`, because no reader can sign
in. `interactions.user_id` has been in the frozen E0.2 contract since day
one and is NULL on every row ever written.

This migration closes that, and two adjacent gaps found with it (F136).

## Readers are not staff, and this is not that table

Staff credentials live in `now_platform.public.users` and are projected
into each city database as shadow rows so Payload can bind to them
(docs/ADMIN-CONSOLIDATION.md). Readers stay here in `engine`, deliberately
separate: the staff shadow is sized for dozens of people and carries
editorial and commerce roles, and a reader must never be one wrong `role`
value away from a CMS session.

What IS shared is the *hashing*, not the store. The `hash`/`salt` columns
below hold PBKDF2 output at `@now/auth`'s parameters — themselves matched
byte-for-byte to Payload's — so one audited hasher serves both
populations. A second hasher is how you end up with two security levels
and only one of them reviewed.

## Why `email_norm` and not just `email`

`uq_identities_email` (0001) is on the RAW column. `Foo@example.com` and
`foo@example.com` are different strings and the same mailbox, so that
constraint would happily let one person register twice and then make
"which row is the account" a live question at every sign-in. The raw
unique is kept — it costs nothing and still forbids exact duplicates —
and the normalised one is added as the constraint that actually holds.

Both are ordinary unique indexes rather than functional ones, following
0006's reasoning: a stored normalised column keeps the constraint
expressible through a schema layer that cannot describe an expression
index.

`email` stays NULLABLE. Postgres unique indexes permit multiple NULLs, so
this costs nothing today and leaves room for an identity that exists
before it has an address. Requiring it is the application's job, where the
rule can differ between a registration and a backfill.

## `identity_tokens` — hashed, because a mailbox is not a safe place

Verification and reset links are bearer credentials: whoever holds the
token is the user. Storing them in plaintext means a database dump is a
set of live password resets. Only a hash goes in, the link carries the
secret, and `consumed_at` makes each one single-use — a reset link that
still works after it has been used is a reset link someone can replay out
of a forwarded email.

There is no `updated_at`: a token is never updated, only consumed.

## `saved_items` — the signal with nowhere to go

ARCHITECTURE §10 weights `saved / shared` at **1.0**, the strongest signal
after adding a stop to an itinerary, and there has never been a table to
record one in.

`entity_id` is `text`, not bigint, following the widening precedent set by
0005 for sibling entity refs. Articles, places and events do not share a
key type today and betting that they always will is how 0005 happened.

`site_id` takes a real FK to `engine.sites`, unlike 0006's `site_slug`.
The reasoning differs because the row does: a newsletter subscription is a
consent record that should outlive a masthead being renamed or retired,
while a save is a pointer into one site's content and is meaningless
without it.
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "0007"
down_revision: Union[str, None] = "0006"
branch_labels: Union[Sequence[str], str, None] = None
depends_on: Union[Sequence[str], str, None] = None


def upgrade() -> None:
    # --- credentials on the existing reader identity -----------------------
    #
    # Every column is added NULLable or with a default. `identities` is not
    # empty in every environment, and a NOT NULL without a default would fail
    # the migration on the first deployment that has a row in it.
    op.execute(
        """
        ALTER TABLE engine.identities
            ADD COLUMN IF NOT EXISTS email_norm        text,
            ADD COLUMN IF NOT EXISTS name              text,
            ADD COLUMN IF NOT EXISTS hash              text,
            ADD COLUMN IF NOT EXISTS salt              text,
            ADD COLUMN IF NOT EXISTS email_verified_at timestamptz,
            ADD COLUMN IF NOT EXISTS login_attempts    integer     NOT NULL DEFAULT 0,
            ADD COLUMN IF NOT EXISTS lock_until        timestamptz,
            ADD COLUMN IF NOT EXISTS last_login_at     timestamptz,
            ADD COLUMN IF NOT EXISTS status            text        NOT NULL DEFAULT 'active',
            ADD COLUMN IF NOT EXISTS updated_at        timestamptz NOT NULL DEFAULT now()
        """
    )
    # 'deleted' is a tombstone, not a row that has gone away. A reader who
    # deletes their account must stop being able to sign in immediately, while
    # the `interactions` rows carrying their `user_id` are partitioned and
    # cannot be erased in the same transaction. The tombstone is what makes
    # "signed out everywhere now, erased by the deletion job" expressible.
    op.execute(
        """
        ALTER TABLE engine.identities
            ADD CONSTRAINT identities_status_ck
            CHECK (status IN ('active', 'suspended', 'deleted'))
        """
    )
    # Backfill before the unique index is built, or an environment holding two
    # case-variant addresses fails index creation with a message that names the
    # index rather than the actual problem.
    op.execute(
        """
        UPDATE engine.identities
           SET email_norm = lower(btrim(email))
         WHERE email IS NOT NULL AND email_norm IS NULL
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_identities_email_norm
            ON engine.identities (email_norm)
        """
    )

    # --- single-use email tokens ------------------------------------------
    op.execute(
        """
        CREATE TABLE engine.identity_tokens (
            id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            identity_id uuid        NOT NULL
                        REFERENCES engine.identities(id) ON DELETE CASCADE,
            kind        text        NOT NULL,
            token_hash  text        NOT NULL,
            expires_at  timestamptz NOT NULL,
            consumed_at timestamptz,
            created_at  timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT identity_tokens_kind_ck
                CHECK (kind IN ('verify_email', 'reset_password'))
        )
        """
    )
    # The only lookup on the hot path: someone followed a link, find the token.
    # UNIQUE because a collision here would mean two identities share a reset.
    op.execute(
        """
        CREATE UNIQUE INDEX identity_tokens_hash_uq
            ON engine.identity_tokens (token_hash)
        """
    )
    # Invalidating a person's outstanding tokens — on password change, on
    # address change, on account deletion — is a per-identity sweep.
    op.execute(
        """
        CREATE INDEX identity_tokens_identity_kind_ix
            ON engine.identity_tokens (identity_id, kind)
        """
    )
    # The expiry reaper. Partial: consumed rows are deleted by the same job and
    # indexing them costs writes on every single successful verification.
    op.execute(
        """
        CREATE INDEX identity_tokens_expiry_ix
            ON engine.identity_tokens (expires_at)
            WHERE consumed_at IS NULL
        """
    )

    # --- saved items -------------------------------------------------------
    op.execute(
        """
        CREATE TABLE engine.saved_items (
            identity_id uuid        NOT NULL
                        REFERENCES engine.identities(id) ON DELETE CASCADE,
            site_id     uuid        NOT NULL REFERENCES engine.sites(id),
            entity_type text        NOT NULL,
            entity_id   text        NOT NULL,
            note        text,
            created_at  timestamptz NOT NULL DEFAULT now(),
            PRIMARY KEY (identity_id, site_id, entity_type, entity_id)
        )
        """
    )
    # The dashboard read: this reader's saves, newest first, for one masthead.
    # The primary key cannot serve it — its leading columns are right but it
    # orders by entity_type, not time.
    op.execute(
        """
        CREATE INDEX saved_items_reader_recent_ix
            ON engine.saved_items (identity_id, site_id, created_at DESC)
        """
    )
    # "How many people saved this" — the popularity prior, and the join back
    # from an article to its savers.
    op.execute(
        """
        CREATE INDEX saved_items_entity_ix
            ON engine.saved_items (site_id, entity_type, entity_id)
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS engine.saved_items")
    op.execute("DROP TABLE IF EXISTS engine.identity_tokens")
    op.execute("DROP INDEX IF EXISTS engine.uq_identities_email_norm")
    op.execute(
        "ALTER TABLE engine.identities DROP CONSTRAINT IF EXISTS identities_status_ck"
    )
    # Dropping these discards reader credentials. That is the correct
    # behaviour for a downgrade and worth saying out loud: it is not
    # reversible by re-running the upgrade, because the hashes are gone.
    op.execute(
        """
        ALTER TABLE engine.identities
            DROP COLUMN IF EXISTS email_norm,
            DROP COLUMN IF EXISTS name,
            DROP COLUMN IF EXISTS hash,
            DROP COLUMN IF EXISTS salt,
            DROP COLUMN IF EXISTS email_verified_at,
            DROP COLUMN IF EXISTS login_attempts,
            DROP COLUMN IF EXISTS lock_until,
            DROP COLUMN IF EXISTS last_login_at,
            DROP COLUMN IF EXISTS status,
            DROP COLUMN IF EXISTS updated_at
        """
    )
