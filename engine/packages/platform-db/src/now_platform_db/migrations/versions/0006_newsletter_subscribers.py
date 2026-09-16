"""newsletter subscribers

Revision ID: 0006
Revises: 0005
Create Date: 2026-09-16

The newsletter signup form has been on every page of the reader site since
the comp, posting to `/api/subscribe`. That route has never existed. Every
address anyone typed went nowhere, and the form gave no sign of it.

Platform-level, not per-city, for the same reason `identities` is: a
subscriber is a person, and a person can read both cities. `site_slug`
records which masthead they signed up to so each city can send its own
list, but one row per person per city keeps that a fact about the
subscription rather than a duplicate human.

Cross-database reference note (same rule as 0001): `site_slug` is a plain
`text` column with no FK to `engine.sites`. It is in the same database
here, so a FK would be enforceable — but sites are rows that can be
renamed or retired, and a subscription should survive that rather than
cascade. The application validates the slug.

## Consent and retention

`status` starts at `pending`, never `confirmed`. Nothing in this schema
lets a row become `confirmed` implicitly — that requires a double opt-in
step which does not exist yet, and until it does, no address here should
be mailed. A schema that defaulted to `confirmed` would quietly turn a
form submission into a claim of consent we cannot evidence.

Deliberately NOT stored: IP address, user agent, referrer. They would be
the easiest thing in the world to add here and there is no purpose for
them that justifies holding them.

`email_norm` exists because uniqueness has to be case- and
whitespace-insensitive, and a functional unique index cannot be expressed
through Payload's schema layer later if this table ever moves to `public`.
Storing the normalised form keeps the constraint ordinary.
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[Sequence[str], str, None] = None
depends_on: Union[Sequence[str], str, None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE engine.newsletter_subscribers (
            id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            site_slug    text        NOT NULL,
            email        text        NOT NULL,
            email_norm   text        NOT NULL,
            status       text        NOT NULL DEFAULT 'pending',
            source       text,
            created_at   timestamptz NOT NULL DEFAULT now(),
            confirmed_at timestamptz,
            CONSTRAINT newsletter_subscribers_status_ck
                CHECK (status IN ('pending', 'confirmed', 'unsubscribed'))
        )
        """
    )
    # One subscription per person per masthead. The upsert in the reader app
    # relies on this constraint existing, so a repeat signup is a no-op
    # rather than a duplicate or an error shown to a reader.
    op.execute(
        """
        CREATE UNIQUE INDEX newsletter_subscribers_site_email_uq
            ON engine.newsletter_subscribers (site_slug, email_norm)
        """
    )
    # Sending a city's list is the only read path that matters.
    op.execute(
        """
        CREATE INDEX newsletter_subscribers_site_status_ix
            ON engine.newsletter_subscribers (site_slug, status)
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS engine.newsletter_subscribers")
