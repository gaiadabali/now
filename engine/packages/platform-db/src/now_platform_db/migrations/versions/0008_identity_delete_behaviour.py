"""make a reader account deletable

Revision ID: 0008
Revises: 0007
Create Date: 2026-09-16

E8.4a — closes F138.

Deleting a reader raised a foreign-key violation. Found by actually trying
it on a test account, not by reading the schema:

    ERROR: update or delete on table "identities" violates foreign key
    constraint "user_profiles_user_id_fkey" on table "user_profiles"

`identity_tokens` and `saved_items` (0007) already cascade. `user_profiles`
and `itineraries` came from baseline 0001 with the default `NO ACTION`, so
from E8.4 onward — the moment stating a preference writes a
`user_profiles` row — **every engaged reader became undeletable**.

docs/READER-IDENTITY.md called export-and-delete a launch requirement
rather than something to retrofit. This is the half that was missed.

## The two tables want opposite things

**`user_profiles` cascades.** Taste vectors and facet affinity are derived
from one person's behaviour and mean nothing without them. Keeping the row
after the identity is gone leaves an orphan that no query can attribute and
no subject-access request can find, which is worse than useless — it is a
record of someone's preferences that survives their deletion.

**`itineraries` does NOT cascade — it nulls.** A trip can be shared by
token (§12, E5.4/E5.7), and cascading would make one person's account
deletion silently break a link other people are using. `user_id` is already
nullable, which is the schema saying the same thing: an itinerary may exist
without an owner. So the trip survives, anonymised, and the share token
keeps working. `itinerary_days` and `itinerary_stops` hang off the
itinerary and are untouched by any of this.

That is a judgement call and worth stating plainly: it means deleting an
account does not erase itineraries that person created. They stop being
*attributable* — which is what the deletion has to guarantee — but the
content stays. An erasure request that must also remove the trips is a
different operation, and it should be a deliberate one rather than a side
effect nobody predicted.

## Why not ON DELETE triggers or application-side cleanup

The application could delete children in the right order inside a
transaction. It would also be the only thing standing between a manual
`DELETE` in psql and a foreign-key error at 2am. Referential behaviour that
the database can express belongs in the database; this is exactly the case
Postgres has a clause for.
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "0008"
down_revision: Union[str, None] = "0007"
branch_labels: Union[Sequence[str], str, None] = None
depends_on: Union[Sequence[str], str, None] = None


def upgrade() -> None:
    # Derived data: it has no meaning once the reader is gone.
    op.execute(
        "ALTER TABLE engine.user_profiles DROP CONSTRAINT IF EXISTS user_profiles_user_id_fkey"
    )
    op.execute(
        """
        ALTER TABLE engine.user_profiles
            ADD CONSTRAINT user_profiles_user_id_fkey
            FOREIGN KEY (user_id) REFERENCES engine.identities(id) ON DELETE CASCADE
        """
    )

    # Shared content: it outlives its author, anonymised. `user_id` was
    # already nullable, so no column change is needed for this to be legal.
    op.execute(
        "ALTER TABLE engine.itineraries DROP CONSTRAINT IF EXISTS itineraries_user_id_fkey"
    )
    op.execute(
        """
        ALTER TABLE engine.itineraries
            ADD CONSTRAINT itineraries_user_id_fkey
            FOREIGN KEY (user_id) REFERENCES engine.identities(id) ON DELETE SET NULL
        """
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE engine.user_profiles DROP CONSTRAINT IF EXISTS user_profiles_user_id_fkey"
    )
    op.execute(
        """
        ALTER TABLE engine.user_profiles
            ADD CONSTRAINT user_profiles_user_id_fkey
            FOREIGN KEY (user_id) REFERENCES engine.identities(id)
        """
    )
    op.execute(
        "ALTER TABLE engine.itineraries DROP CONSTRAINT IF EXISTS itineraries_user_id_fkey"
    )
    op.execute(
        """
        ALTER TABLE engine.itineraries
            ADD CONSTRAINT itineraries_user_id_fkey
            FOREIGN KEY (user_id) REFERENCES engine.identities(id)
        """
    )
