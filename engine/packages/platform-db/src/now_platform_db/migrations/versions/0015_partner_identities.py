"""partner identities — the third population

Revision ID: 0015
Revises: 0014
Create Date: 2026-09-26

Phase 0 (P0.1), plan §8.3, pulled forward from Phase 8 (P8.1) into Phase 0
per this ticket's brief and §11a answer 7: "Partner logins are needed now,
not after ten offers. The partner portal... moves up to run alongside the
offers console." The portal's *screens* are not part of this migration —
only the identity store they will authenticate against, so nothing in a
later BE ticket has to touch schema to ship them.

## Why a third table, not a role on `identities` or `engine.orgs`

§8.3's argument, repeated because it is the entire design: "READER-IDENTITY's
argument for two identity stores applies a third time." A partner user acts
*for an organisation* it never authenticates as a reader (it must never
satisfy `identities`) and never as staff (it must never reach
`/team-editor`, which authenticates against `now_platform.public.users`,
a different database schema entirely, owned by Payload). Merging it into
either existing population would make "which population is this token for"
a runtime bug waiting to happen instead of a fact the schema — and the
token's own signing secret and `aud` claim, at the app layer — establish
structurally. `identities`/`identity_tokens` (0007) is the template this
migration mirrors column-for-column, deliberately: same hashing convention
(PBKDF2 `hash`/`salt`, matched to `@now/auth`'s parameters — 0007's own
words, "one audited hasher serves both populations", now a third), same
lockout counters, same hashed single-use tokens. A second, independently
reviewed hasher is how a project ends up with three security levels instead
of one; reusing the parameters is not reusing the *store*.

## `org_id`, not `site_id` — this population is scoped along the other axis

Every other Phase 0 table added in this set is site-scoped (§3-§7's
`(site_id, ...)` pattern) because it is about a masthead's readers or a
masthead's commerce. A partner is scoped to the organisation it belongs to,
which can itself hold partnerships across more than one site (0001's
`orgs.parent_org_id`, and `partnerships.org_id` with no `site_id` filter on
the org itself) — the whole reason the portal's scope rule (§8.3) reads "org
id from the session", not "site id from the session". `UNIQUE (org_id,
email_norm)` rather than a single global email uniqueness deliberately
allows the same mailbox to hold separate logins at two different partner
organisations, unlike `identities.email_norm` — a partner is not assumed to
be a single person tied to one email for life the way a reader account is;
the unit that matters here is "this person's access to this org".

## `partner_user_tokens` — same shape as `identity_tokens`, same reason

Verification and invitation links are bearer credentials; only a hash is
stored, matching 0007's "a mailbox is not a safe place" and 0011's manage
token. `kind` adds `invite` to 0007's `verify_email`/`reset_password`
vocabulary — P8.1's "invitation by a `partner_manager`" flow needs a
single-use, expiring, hashed link the same way a password reset does, and
inventing a separate mechanism for it would be a second thing to secure and
audit for no product reason.

## Deliberately NOT built in this migration

No RLS policy on these two tables (0017 does not touch them) and no
`current_org_id()` session-variable helper: the portal's own access model
(P8.1 — "a third identity population on the same origin as staff and
readers; the boundary is the whole risk", flagged `opus·high` in the
roadmap) is a bigger and more specific design question than this
foundations ticket should answer by fiat, and an RLS policy written before
the session/cookie/`aud` design exists would be guessing at what
`current_setting('app.org_id')` is even supposed to mean for a console
query that legitimately spans one org across two sites. What this
migration guarantees instead: the table exists, is hashed the same way
every other credential store in this schema is, and grants nothing to
`now_runtime` beyond ordinary CRUD (0017's grants section) until P8.1 adds
the scoping policy on top of it.
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "0015"
down_revision: Union[str, None] = "0014"
branch_labels: Union[Sequence[str], str, None] = None
depends_on: Union[Sequence[str], str, None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE engine.partner_users (
            id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            org_id             uuid NOT NULL REFERENCES engine.orgs(id) ON DELETE CASCADE,
            email              text NOT NULL,
            email_norm         text NOT NULL,
            name               text,
            hash               text,
            salt               text,
            role               text NOT NULL DEFAULT 'partner_user'
                               CHECK (role IN ('partner_user', 'partner_admin')),
            status             text NOT NULL DEFAULT 'invited'
                               CHECK (status IN ('invited', 'active', 'suspended', 'deleted')),
            email_verified_at  timestamptz,
            login_attempts     integer NOT NULL DEFAULT 0,
            lock_until         timestamptz,
            last_login_at      timestamptz,
            -- The staff user (now_platform.public.users, Payload-owned) who
            -- sent the invitation. Cross-schema-but-same-database, and kept
            -- a bare uuid with no FK anyway: `public` does not exist yet in
            -- this database (ARCHITECTURE.md §2/this package's README), so
            -- there is nothing to reference today, and when it lands this
            -- becomes an ordinary same-database FK, not a rewrite.
            invited_by         uuid,
            created_at         timestamptz NOT NULL DEFAULT now(),
            updated_at         timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT uq_partner_users_org_email UNIQUE (org_id, email_norm)
        )
        """
    )
    op.execute("CREATE INDEX ix_partner_users_org ON engine.partner_users (org_id)")

    op.execute(
        """
        CREATE TABLE engine.partner_user_tokens (
            id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            partner_user_id  uuid NOT NULL
                             REFERENCES engine.partner_users(id) ON DELETE CASCADE,
            kind             text NOT NULL,
            token_hash       text NOT NULL,
            expires_at       timestamptz NOT NULL,
            consumed_at      timestamptz,
            created_at       timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT partner_user_tokens_kind_ck
                CHECK (kind IN ('invite', 'verify_email', 'reset_password'))
        )
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX partner_user_tokens_hash_uq
            ON engine.partner_user_tokens (token_hash)
        """
    )
    op.execute(
        """
        CREATE INDEX partner_user_tokens_partner_user_kind_ix
            ON engine.partner_user_tokens (partner_user_id, kind)
        """
    )
    op.execute(
        """
        CREATE INDEX partner_user_tokens_expiry_ix
            ON engine.partner_user_tokens (expires_at)
            WHERE consumed_at IS NULL
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS engine.partner_user_tokens")
    op.execute("DROP TABLE IF EXISTS engine.partner_users")
