"""partner offers and vouchers

Revision ID: 0012
Revises: 0011
Create Date: 2026-09-26

Phase 0 (P0.1), plan §7.2, folded forward from the roadmap's Phase 6 into
Phase 0 per this ticket's brief and the owner's §11a answer 7 ("partner
logins are needed now... the partner portal moves up to run alongside the
offers console") — the data model for offers has to exist before either
the offers console or the partner portal (0015) can be built, and before
P0.4's RLS migration can add policies to it.

Lands before the itinerary reshape (0013): `destinations.offer_id` and
`itinerary_stops.offer_id` (§3.2) both reference `engine.offers(id)`, so
this table has to exist first for those FKs to resolve. `voucher_claims.
itinerary_id` references `engine.itineraries(id)`, which already exists
(0001) — no ordering problem there.

## The owner's ruling narrows §7.1's proposal

The plan's open question 1 proposed `listed` and `paid` partnerships could
both issue offers. §11a answer 1 is narrower and final: "Offers are a
partner benefit: only venues under an active paid partnership issue them."
That is enforced here, not left to the console, with a trigger rather than
a `CHECK` — a `CHECK` constraint cannot reference another table, and "is
`partnership_id` a `paid` partnership" is exactly a cross-table fact. The
trigger fires on INSERT and on UPDATE of `partnership_id` (an offer moved
to point at a different partnership must be re-validated the same way a
new one is); it deliberately does not also require `status = 'active'`
here — an offer can legitimately be drafted against a partnership that
starts next week, and `partnerships_active`/`partnership_is_effective`
(0003) already answer the *is it live right now* question at read time for
whatever screen needs it. Tier is a durable classification of the
commercial relationship; liveness is a point-in-time fact — conflating them
in one trigger would make a perfectly normal "draft an offer ahead of the
partnership's start date" workflow fail at INSERT.

## `offer_places` is deliberately not derived from `partnerships.place_id`

A `paid` partnership can be org-level (`partnerships.place_id IS NULL`,
`org_id` set — 0001's `ck_partnerships_org_xor_place`) covering every venue
under that org, while an offer's terms ("15% off dinner") are almost always
venue-specific even when the partner is a restaurant group. `offer_places`
is therefore its own explicit list, one row per `(site_id, place_id)` the
offer applies to, rather than inherited implicitly from the partnership's
scope — the same reasoning the plan gives for `destinations` not being a
flagged `saved_items` row: an implicit derivation would need its own
converter the moment the two diverge (an org-level partner runs an offer at
three of its five venues), and it is the explicit list that the console,
the claim/redeem flow and `offer_events` reporting all read directly.

## Redemption modes and the fraud posture they encode (§7.1/§7.3)

Three modes, one `redemption_mode` CHECK, because the three are mutually
exclusive per offer, not a set of flags: `shared_code` (lowest control,
venue applies the deal on trust), `reader_confirm` (the reader's own
irreversible swipe is the record), `unique_code` (a per-claim HMAC-derived
code the venue's PIN confirms). `venue_pin_hash` is hashed for the same
reason every bearer/shared secret in this schema is (0007's identity
tokens, 0011's manage token) — the PIN is compared, never displayed back,
and a database dump does not hand out every venue's redemption PIN.

## `voucher_claims.code` is UNIQUE, nullable, mode-conditional

Only meaningful for `unique_code` mode (NULL otherwise, per §7.2's own
comment) — a partial-would-be unique index is not used here because a
plain `UNIQUE` already permits multiple NULLs in Postgres, which is exactly
"most claims have no code" without needing a WHERE clause. `claim_ip_hash`
follows the same hash-not-raw-address convention as 0011's consent columns
— it exists for the "20 claims/day/IP-hash" rate limit (§7.3) and the daily
anomaly line, not as a re-identifiable record.

## `offer_events` is partitioned like `ad_events`, and NOT reused as it

§7.2's own note: `ad_events` requires a `placement_id` and models a booked
slot's impressions; an offer is claimed and redeemed by an identity, has no
placement, and its funnel (impression → view → claim → redeem → expire /
revoke) is a different state machine than impression/click/conversion.
Partitioned by `ts` RANGE, same convention as `ad_events` (0001) and
`interactions`/`impressions` in the city DB — this is the partner funnel
reporting table, high write volume, no updates ever. Added to
`now_platform_db.partitions.PARTITIONED_TABLES` in the same commit so
`now-platform-db ensure-partitions`/`drop-old-partitions` manage it for
free; `schema_hash`'s partition-exclusion pattern is widened alongside it
(see that file's diff) or the drift gate would flag every new daily child
table as an unexpected table forever.

## `offer_audit` mirrors `partnership_audit` exactly

Same shape (`before`/`after` jsonb, `actor_id`, `ts`) as 0001's
`partnership_audit`, for the same reason: "Approval is editorial-adjacent"
(§7.4) needs the same before/after trail a partnership change gets, and a
second audit shape for a second commercial object would be a second thing
to remember when auditing "did anyone tamper with a claim/approval".
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "0012"
down_revision: Union[str, None] = "0011"
branch_labels: Union[Sequence[str], str, None] = None
depends_on: Union[Sequence[str], str, None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE engine.offers (
            id                       uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            partnership_id           uuid NOT NULL REFERENCES engine.partnerships(id),
            org_id                   uuid REFERENCES engine.orgs(id),
            site_id                  uuid NOT NULL REFERENCES engine.sites(id),
            campaign_id              uuid REFERENCES engine.campaigns(id),
            title                    text NOT NULL,
            summary                  text,
            terms                    text,
            kind                     text NOT NULL
                                     CHECK (kind IN ('percent_off', 'amount_off', 'freebie', 'bundle')),
            value_pct                numeric,
            value_idr                integer,
            redemption_mode          text NOT NULL
                                     CHECK (redemption_mode IN ('shared_code', 'reader_confirm', 'unique_code')),
            validity_kind            text NOT NULL DEFAULT 'open'
                                     CHECK (validity_kind IN ('open', 'fixed_date')),
            fixed_date               date,
            shared_code              text,
            valid_from               timestamptz NOT NULL,
            valid_to                 timestamptz NOT NULL,
            weekdays                 smallint[] NOT NULL DEFAULT '{0,1,2,3,4,5,6}',
            hours_from               time,
            hours_to                 time,
            blackout_dates           date[] NOT NULL DEFAULT '{}',
            total_cap                integer,
            daily_cap                integer,
            per_reader_cap           integer NOT NULL DEFAULT 1,
            claim_ttl_hours          integer NOT NULL DEFAULT 72,
            min_spend_idr            integer,
            requires_verified_email  boolean NOT NULL DEFAULT true,
            status                   text NOT NULL DEFAULT 'draft'
                                     CHECK (status IN
                                         ('draft', 'pending_approval', 'live', 'paused', 'ended', 'rejected')),
            approved_by              uuid,
            approved_at              timestamptz,
            venue_pin_hash           text,
            created_by               uuid,
            created_at               timestamptz NOT NULL DEFAULT now(),
            updated_at               timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT offers_valid_window_ck CHECK (valid_to > valid_from)
        )
        """
    )
    op.execute("CREATE INDEX ix_offers_site ON engine.offers (site_id)")
    op.execute("CREATE INDEX ix_offers_partnership ON engine.offers (partnership_id)")
    op.execute("CREATE INDEX ix_offers_org ON engine.offers (org_id) WHERE org_id IS NOT NULL")
    # The reader-facing hot path: this site's currently-live offers.
    op.execute(
        """
        CREATE INDEX ix_offers_live
            ON engine.offers (site_id, valid_from, valid_to)
            WHERE status = 'live'
        """
    )

    # §11a.1 — only a `paid` partnership may have an offer attached to it.
    op.execute(
        """
        CREATE OR REPLACE FUNCTION engine.offers_require_paid_partnership()
        RETURNS trigger AS $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM engine.partnerships
                 WHERE id = NEW.partnership_id AND tier = 'paid'
            ) THEN
                RAISE EXCEPTION
                    'engine.offers.partnership_id % is not a paid partnership '
                    '(owner ruling, ITINERARY-AND-READER-PRODUCTS-PLAN.md section 11a.1: '
                    'offers are a paid-partnership benefit)',
                    NEW.partnership_id
                    USING ERRCODE = 'check_violation';
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.execute(
        """
        CREATE TRIGGER offers_require_paid_partnership_trg
            BEFORE INSERT OR UPDATE OF partnership_id ON engine.offers
            FOR EACH ROW EXECUTE FUNCTION engine.offers_require_paid_partnership()
        """
    )

    op.execute(
        """
        CREATE TABLE engine.offer_places (
            offer_id  uuid NOT NULL REFERENCES engine.offers(id) ON DELETE CASCADE,
            site_id   uuid NOT NULL REFERENCES engine.sites(id),
            place_id  text NOT NULL,
            PRIMARY KEY (offer_id, site_id, place_id)
        )
        """
    )
    # The place-page read: every live offer at this (site, place).
    op.execute("CREATE INDEX ix_offer_places_place ON engine.offer_places (site_id, place_id)")

    op.execute(
        """
        CREATE TABLE engine.voucher_claims (
            id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            offer_id          uuid NOT NULL REFERENCES engine.offers(id),
            identity_id       uuid NOT NULL REFERENCES engine.identities(id) ON DELETE CASCADE,
            code              text UNIQUE,
            itinerary_id      uuid REFERENCES engine.itineraries(id) ON DELETE SET NULL,
            status            text NOT NULL
                              CHECK (status IN ('claimed', 'redeemed', 'expired', 'revoked')),
            claimed_at        timestamptz NOT NULL DEFAULT now(),
            expires_at        timestamptz NOT NULL,
            redeemed_at       timestamptz,
            redeemed_via      text,
            redeemed_place_id text,
            redeemed_by       text,
            claim_ip_hash     text,
            claim_anon_id     uuid
        )
        """
    )
    op.execute("CREATE INDEX ix_voucher_claims_offer ON engine.voucher_claims (offer_id)")
    # "Wallet" read: this reader's claims, soonest-expiring first (§7.3's
    # "expiring-soon claims are grouped first").
    op.execute(
        """
        CREATE INDEX ix_voucher_claims_identity_wallet
            ON engine.voucher_claims (identity_id, expires_at)
            WHERE status = 'claimed'
        """
    )
    # Cap enforcement at claim time: per-reader, per-offer, counting
    # claimed+redeemed (§7.3's "not expired").
    op.execute(
        """
        CREATE INDEX ix_voucher_claims_cap_check
            ON engine.voucher_claims (offer_id, identity_id)
            WHERE status IN ('claimed', 'redeemed')
        """
    )
    # The nightly expiry sweep (§7.3 EXPIRE).
    op.execute(
        """
        CREATE INDEX ix_voucher_claims_expiry
            ON engine.voucher_claims (expires_at)
            WHERE status = 'claimed'
        """
    )

    op.execute(
        """
        CREATE TABLE engine.offer_events (
            id           uuid NOT NULL DEFAULT gen_random_uuid(),
            offer_id     uuid NOT NULL REFERENCES engine.offers(id),
            kind         text NOT NULL
                         CHECK (kind IN ('impression', 'view', 'claim', 'redeem', 'expire', 'revoke')),
            identity_id  uuid REFERENCES engine.identities(id) ON DELETE SET NULL,
            session_id   uuid,
            surface      text,
            ts           timestamptz NOT NULL DEFAULT now(),
            PRIMARY KEY (id, ts)
        ) PARTITION BY RANGE (ts)
        """
    )
    op.execute("CREATE INDEX ix_offer_events_offer ON engine.offer_events (offer_id, ts DESC)")

    op.execute(
        """
        CREATE TABLE engine.offer_audit (
            id        uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            offer_id  uuid NOT NULL REFERENCES engine.offers(id),
            actor_id  uuid,
            before    jsonb,
            after     jsonb,
            ts        timestamptz NOT NULL DEFAULT now()
        )
        """
    )
    op.execute("CREATE INDEX ix_offer_audit_offer ON engine.offer_audit (offer_id, ts DESC)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS engine.offer_audit")
    op.execute("DROP TABLE IF EXISTS engine.offer_events")
    op.execute("DROP TABLE IF EXISTS engine.voucher_claims")
    op.execute("DROP TABLE IF EXISTS engine.offer_places")
    op.execute("DROP TRIGGER IF EXISTS offers_require_paid_partnership_trg ON engine.offers")
    op.execute("DROP FUNCTION IF EXISTS engine.offers_require_paid_partnership()")
    op.execute("DROP TABLE IF EXISTS engine.offers")
