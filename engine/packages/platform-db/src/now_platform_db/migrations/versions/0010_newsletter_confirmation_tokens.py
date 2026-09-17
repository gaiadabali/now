"""newsletter confirmation tokens

Revision ID: 0010
Revises: 0009
Create Date: 2026-09-17

E8.1b — closes F135.

Migration 0006 created `newsletter_subscribers` with a
`pending → confirmed → unsubscribed` status and said so plainly in its own
docstring: *"Nothing in this schema lets a row become `confirmed`
implicitly — that requires a double opt-in step which does not exist
yet, and until it does, no address here should be mailed."*

It still does not exist. The form has been live on both cities since the
sites went up, every address lands as `pending`, nothing is ever sent, and
the page tells the reader *"You are on the list… the next edition will
arrive on schedule."* None of that is true. It is the same shape as F141
on the account surface: not a failure, a **wrong success**, told
confidently to the person it is wrong about.

This adds the one thing the state machine was missing — a way for a
subscriber to prove they own the address.

## Why a column and not `identity_tokens`

0007's `identity_tokens` hangs off `engine.identities` with a cascading
foreign key, and a newsletter subscriber is **not** an identity: no
account, no credential, and quite deliberately no requirement to have one.
Pointing that table at two different parents, or making every subscriber an
identity row so the FK has something to reference, would both be worse than
two columns here.

## Hashed, like every other emailed token

Only the SHA-256 goes in the table; the secret travels in the link. A
database dump should not be a set of live confirmations someone can replay
— the same reasoning as `identity_tokens.token_hash` (0007), and cheap:
the token is CSPRNG output, so a plain digest is enough and there is
nothing to brute-force.

`confirm_expires_at` bounds it. An unconfirmed row is not deleted when it
lapses — it stays `pending` as a record that someone once asked, which is
what makes "we already have an unconfirmed request for this address"
answerable without guessing.
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "0010"
down_revision: Union[str, None] = "0009"
branch_labels: Union[Sequence[str], str, None] = None
depends_on: Union[Sequence[str], str, None] = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE engine.newsletter_subscribers
            ADD COLUMN IF NOT EXISTS confirm_token_hash text,
            ADD COLUMN IF NOT EXISTS confirm_expires_at timestamptz,
            ADD COLUMN IF NOT EXISTS confirm_sent_at    timestamptz,
            ADD COLUMN IF NOT EXISTS unsubscribed_at    timestamptz
        """
    )
    # The lookup a confirmation link performs, and the only one on this table
    # that has to be fast. UNIQUE because a collision would confirm the wrong
    # person's subscription.
    #
    # Partial: a confirmed or lapsed row keeps its hash for audit but is not
    # worth indexing, and every confirmation would otherwise pay to maintain
    # an entry nothing will ever look up again.
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS newsletter_confirm_token_uq
            ON engine.newsletter_subscribers (confirm_token_hash)
         WHERE confirm_token_hash IS NOT NULL
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS engine.newsletter_confirm_token_uq")
    op.execute(
        """
        ALTER TABLE engine.newsletter_subscribers
            DROP COLUMN IF EXISTS confirm_token_hash,
            DROP COLUMN IF EXISTS confirm_expires_at,
            DROP COLUMN IF EXISTS confirm_sent_at,
            DROP COLUMN IF EXISTS unsubscribed_at
        """
    )
