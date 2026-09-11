"""baseline engine schema for now_platform

Revision ID: 0001
Revises:
Create Date: 2026-09-08

Creates every table platform-side services need before a Payload instance
exists for `now_platform.public` (ARCHITECTURE.md §2 diagram shows some of
these — sites, orgs, partnerships, campaigns, placements — eventually owned
by such an instance). Per E0.2's task brief, everything is placed under
`now_platform.engine` for now: "own both schemas conceptually in
now_platform, but only create engine there; a Payload instance will own
platform public later." Nothing here creates a `public` table. When that
Payload instance lands, moving a table from `engine` to `public` is a
follow-up migration + a one-time `ALTER TABLE ... SET SCHEMA`, not a rewrite.

Fixed external contract (do not change without updating consumers):
    sites(id, slug, hostname, name, locale, timezone, currency,
          brand_tokens jsonb, nav jsonb, home_rails jsonb,
          ranking_weights jsonb, db_ref text, enabled_modules text[], status)
  consumed by: engine-api (now_config.SiteConfig), site:create/site:migrate.

Cross-database references (a `place_id` living in a city DB, an
`origin_article_id` living in a city DB) are stored as plain `uuid` columns
with NO foreign key — Postgres cannot enforce a constraint across databases,
and DB-per-city means the referenced row lives elsewhere by design
(ARCHITECTURE.md §2, §3.5 syndications). Referential integrity for those
columns is an application/worker responsibility.
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[Sequence[str], str, None] = None
depends_on: Union[Sequence[str], str, None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")
    # engine schema itself is created by env.py before the version table is
    # stamped, so every migration (including this one) can assume it exists.

    op.execute(
        """
        CREATE TABLE engine.sites (
            id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            slug             text NOT NULL,
            hostname         text NOT NULL,
            name             text NOT NULL,
            locale           text NOT NULL DEFAULT 'en',
            timezone         text NOT NULL,
            currency         text NOT NULL,
            brand_tokens     jsonb NOT NULL DEFAULT '{}'::jsonb,
            nav              jsonb NOT NULL DEFAULT '{}'::jsonb,
            home_rails       jsonb NOT NULL DEFAULT '{}'::jsonb,
            ranking_weights  jsonb NOT NULL DEFAULT '{}'::jsonb,
            db_ref           text NOT NULL,
            enabled_modules  text[] NOT NULL DEFAULT '{}'::text[],
            status           text NOT NULL DEFAULT 'provisioning'
                                 CHECK (status IN ('active', 'provisioning', 'disabled')),
            created_at       timestamptz NOT NULL DEFAULT now(),
            updated_at       timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT uq_sites_slug UNIQUE (slug),
            CONSTRAINT uq_sites_hostname UNIQUE (hostname),
            CONSTRAINT uq_sites_db_ref UNIQUE (db_ref)
        )
        """
    )

    op.execute(
        """
        CREATE TABLE engine.orgs (
            id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            parent_org_id  uuid REFERENCES engine.orgs (id),
            name           text NOT NULL,
            slug           text NOT NULL,
            website        text,
            booking_url    text,
            logo_media_id  uuid,
            type           text,
            created_at     timestamptz NOT NULL DEFAULT now(),
            updated_at     timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT uq_orgs_slug UNIQUE (slug)
        )
        """
    )
    op.execute("CREATE INDEX ix_orgs_parent ON engine.orgs (parent_org_id)")

    op.execute(
        """
        CREATE TABLE engine.partnerships (
            id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            org_id              uuid NOT NULL REFERENCES engine.orgs (id),
            place_id            uuid NOT NULL,  -- city DB places.id, no FK (cross-database)
            site_id             uuid NOT NULL REFERENCES engine.sites (id),
            tier                text NOT NULL CHECK (tier IN ('free', 'listed', 'paid')),
            starts_at           timestamptz,
            ends_at             timestamptz,
            status              text NOT NULL DEFAULT 'active'
                                    CHECK (status IN ('active', 'paused', 'ended')),
            link_policy         jsonb NOT NULL DEFAULT '{}'::jsonb,
            custom_url          text,
            utm_template        text,
            show_badge          boolean NOT NULL DEFAULT false,
            badge_label         text,
            itinerary_eligible  boolean NOT NULL DEFAULT false,
            boost_cap           numeric(5, 4),
            created_at          timestamptz NOT NULL DEFAULT now(),
            updated_at          timestamptz NOT NULL DEFAULT now()
        )
        """
    )
    op.execute("CREATE INDEX ix_partnerships_org ON engine.partnerships (org_id)")
    op.execute("CREATE INDEX ix_partnerships_site ON engine.partnerships (site_id)")
    op.execute("CREATE INDEX ix_partnerships_place ON engine.partnerships (site_id, place_id)")
    # The hot lookup at render time is "is there an active partnership for
    # this (site, place) right now" — partial index keeps it cheap regardless
    # of how many lapsed/paused partnerships accumulate.
    op.execute(
        """
        CREATE INDEX ix_partnerships_active
            ON engine.partnerships (site_id, place_id)
            WHERE status = 'active'
        """
    )

    op.execute(
        """
        CREATE TABLE engine.partnership_audit (
            id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            partnership_id  uuid NOT NULL REFERENCES engine.partnerships (id),
            actor_id        uuid,
            before          jsonb,
            after           jsonb,
            ts              timestamptz NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        "CREATE INDEX ix_partnership_audit_partnership ON engine.partnership_audit (partnership_id, ts DESC)"
    )

    op.execute(
        """
        CREATE TABLE engine.campaigns (
            id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            org_id      uuid NOT NULL REFERENCES engine.orgs (id),
            site_id     uuid NOT NULL REFERENCES engine.sites (id),
            objective   text,
            budget      numeric(12, 2),
            pacing      text,
            targeting   jsonb NOT NULL DEFAULT '{}'::jsonb,
            status      text NOT NULL DEFAULT 'draft'
                            CHECK (status IN ('draft', 'active', 'paused', 'ended')),
            created_at  timestamptz NOT NULL DEFAULT now(),
            updated_at  timestamptz NOT NULL DEFAULT now()
        )
        """
    )
    op.execute("CREATE INDEX ix_campaigns_site ON engine.campaigns (site_id)")
    op.execute("CREATE INDEX ix_campaigns_org ON engine.campaigns (org_id)")

    op.execute(
        """
        CREATE TABLE engine.placements (
            id                       uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            campaign_id              uuid NOT NULL REFERENCES engine.campaigns (id),
            surface                  text NOT NULL,
            slot                     text NOT NULL,
            boost_factor             numeric(6, 4) NOT NULL DEFAULT 1.0,
            guaranteed_impressions   integer,
            freq_cap                 integer,
            created_at               timestamptz NOT NULL DEFAULT now()
        )
        """
    )
    op.execute("CREATE INDEX ix_placements_campaign ON engine.placements (campaign_id)")

    # Append-only ledger, partitioned daily (mirrors interactions/impressions
    # in the city DB engine schema). This is the invoice basis (ARCHITECTURE.md
    # §11) so it must never be UPDATE'd/DELETE'd in place — see
    # `now_platform_db.partitions` for the rotation job and the follow-up note
    # about revoking UPDATE/DELETE from the runtime role once that role exists.
    op.execute(
        """
        CREATE TABLE engine.ad_events (
            id            uuid NOT NULL DEFAULT gen_random_uuid(),
            campaign_id   uuid NOT NULL REFERENCES engine.campaigns (id),
            placement_id  uuid NOT NULL REFERENCES engine.placements (id),
            session_id    uuid NOT NULL,
            kind          text NOT NULL CHECK (kind IN ('impression', 'click', 'conversion')),
            ts            timestamptz NOT NULL DEFAULT now(),
            PRIMARY KEY (id, ts)
        ) PARTITION BY RANGE (ts)
        """
    )
    op.execute("CREATE INDEX ix_ad_events_campaign ON engine.ad_events (campaign_id, ts DESC)")
    op.execute("CREATE INDEX ix_ad_events_placement ON engine.ad_events (placement_id, ts DESC)")

    op.execute(
        """
        CREATE TABLE engine.facets (
            id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            key          text NOT NULL,
            label        text NOT NULL,
            cardinality  text NOT NULL CHECK (cardinality IN ('single', 'multi')),
            required     boolean NOT NULL DEFAULT false,
            CONSTRAINT uq_facets_key UNIQUE (key)
        )
        """
    )

    op.execute(
        """
        CREATE TABLE engine.terms (
            id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            facet_id    uuid NOT NULL REFERENCES engine.facets (id),
            slug        text NOT NULL,
            label       text NOT NULL,
            parent_id   uuid REFERENCES engine.terms (id),
            geo         geography(Point, 4326),
            embedding   vector(1536),
            created_at  timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT uq_terms_facet_slug UNIQUE (facet_id, slug)
        )
        """
    )
    op.execute("CREATE INDEX ix_terms_parent ON engine.terms (parent_id)")
    op.execute("CREATE INDEX ix_terms_facet ON engine.terms (facet_id)")
    # GiST for location-tree terms that carry a centroid (§8.G).
    op.execute("CREATE INDEX ix_terms_geo ON engine.terms USING gist (geo)")
    # HNSW for term-embedding kNN (used to seed cold-start taste vectors).
    op.execute(
        "CREATE INDEX ix_terms_embedding_hnsw ON engine.terms "
        "USING hnsw (embedding vector_cosine_ops) WHERE embedding IS NOT NULL"
    )

    op.execute(
        """
        CREATE TABLE engine.identities (
            id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            email         text,
            created_at    timestamptz NOT NULL DEFAULT now(),
            stated_prefs  jsonb NOT NULL DEFAULT '{}'::jsonb,
            CONSTRAINT uq_identities_email UNIQUE (email)
        )
        """
    )

    op.execute(
        """
        CREATE TABLE engine.user_profiles (
            user_id          uuid NOT NULL REFERENCES engine.identities (id),
            site_id          uuid NOT NULL REFERENCES engine.sites (id),
            taste_vec_long   vector(1536),
            taste_vec_short  vector(1536),
            facet_affinity   jsonb NOT NULL DEFAULT '{}'::jsonb,
            n_meaningful     integer NOT NULL DEFAULT 0,
            updated_at       timestamptz NOT NULL DEFAULT now(),
            PRIMARY KEY (user_id, site_id)
        )
        """
    )
    op.execute(
        "CREATE INDEX ix_user_profiles_taste_long_hnsw ON engine.user_profiles "
        "USING hnsw (taste_vec_long vector_cosine_ops) WHERE taste_vec_long IS NOT NULL"
    )

    op.execute(
        """
        CREATE TABLE engine.itineraries (
            id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            site_id      uuid NOT NULL REFERENCES engine.sites (id),
            user_id      uuid REFERENCES engine.identities (id),
            title        text,
            start_date   date,
            party        jsonb NOT NULL DEFAULT '{}'::jsonb,
            prefs        jsonb NOT NULL DEFAULT '{}'::jsonb,
            share_token  text,
            created_at   timestamptz NOT NULL DEFAULT now(),
            updated_at   timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT uq_itineraries_share_token UNIQUE (share_token)
        )
        """
    )
    op.execute("CREATE INDEX ix_itineraries_site ON engine.itineraries (site_id)")
    op.execute("CREATE INDEX ix_itineraries_user ON engine.itineraries (user_id)")

    op.execute(
        """
        CREATE TABLE engine.itinerary_days (
            id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            itinerary_id  uuid NOT NULL REFERENCES engine.itineraries (id) ON DELETE CASCADE,
            day_index     integer NOT NULL,
            area_term_id  uuid REFERENCES engine.terms (id),
            CONSTRAINT uq_itinerary_days_seq UNIQUE (itinerary_id, day_index)
        )
        """
    )

    op.execute(
        """
        CREATE TABLE engine.itinerary_stops (
            id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            day_id        uuid NOT NULL REFERENCES engine.itinerary_days (id) ON DELETE CASCADE,
            seq           integer NOT NULL,
            slot          text,
            place_id      uuid NOT NULL,  -- city DB places.id, no FK (cross-database)
            start_time    time,
            duration_min  integer,
            note          text,
            source        text,
            campaign_id   uuid REFERENCES engine.campaigns (id),
            CONSTRAINT uq_itinerary_stops_seq UNIQUE (day_id, seq)
        )
        """
    )

    op.execute(
        """
        CREATE TABLE engine.syndications (
            id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            origin_site        uuid NOT NULL REFERENCES engine.sites (id),
            origin_article_id  uuid NOT NULL,  -- city DB articles.id, no FK (cross-database)
            target_site        uuid NOT NULL REFERENCES engine.sites (id),
            target_path        text,
            published_at       timestamptz,
            created_at         timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT uq_syndications_edge UNIQUE (origin_site, origin_article_id, target_site)
        )
        """
    )
    op.execute("CREATE INDEX ix_syndications_target ON engine.syndications (target_site)")


def downgrade() -> None:
    # Reverse dependency order. Safe pre-data; do not run against a live
    # platform DB without a backup — see package README "Rollout notes".
    op.execute("DROP TABLE IF EXISTS engine.syndications")
    op.execute("DROP TABLE IF EXISTS engine.itinerary_stops")
    op.execute("DROP TABLE IF EXISTS engine.itinerary_days")
    op.execute("DROP TABLE IF EXISTS engine.itineraries")
    op.execute("DROP TABLE IF EXISTS engine.user_profiles")
    op.execute("DROP TABLE IF EXISTS engine.identities")
    op.execute("DROP TABLE IF EXISTS engine.terms")
    op.execute("DROP TABLE IF EXISTS engine.facets")
    op.execute("DROP TABLE IF EXISTS engine.ad_events")
    op.execute("DROP TABLE IF EXISTS engine.placements")
    op.execute("DROP TABLE IF EXISTS engine.campaigns")
    op.execute("DROP TABLE IF EXISTS engine.partnership_audit")
    op.execute("DROP TABLE IF EXISTS engine.partnerships")
    op.execute("DROP TABLE IF EXISTS engine.orgs")
    op.execute("DROP TABLE IF EXISTS engine.sites")
