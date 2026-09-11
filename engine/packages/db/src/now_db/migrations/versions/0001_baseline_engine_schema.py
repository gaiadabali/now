"""baseline engine schema for city databases (now_jakarta, now_bali, ...)

Revision ID: 0001
Revises:
Create Date: 2026-09-08

Applied identically to every city DB by `site:create` / `site:migrate`
(ARCHITECTURE.md §2, "Migration discipline"). Nothing in here may reference
a specific site — see §3.5's ban on `if (site === 'bali')`.

FIXED CONTRACT with the beacon client (E0.4) — column sets below are
authoritative per the E0.2 task brief and must not change without updating
the beacon payload + the `/v1/{site}/events` handler (E0.5):

    interactions(id, anon_id, user_id, session_id, entity_type, entity_id,
                 kind, surface, rail, position, dwell_ms, scroll_pct,
                 referrer, utm jsonb, device, ts)
      kind IN ('view','scroll','dwell','click','outbound','search','exit','thumbs_down')

    impressions(id, session_id, anon_id, surface, rail, entity_id, position, ts)

This is a strict superset of the abbreviated listing in ARCHITECTURE.md §5
(which omits `rail`/`referrer`/`utm`/`device` on interactions and the `id`
PK on impressions) — see this migration's PR description / E0.2 report for
the explicit reconciliation. No column ARCHITECTURE.md §5 requires is
missing or renamed.

`entity_id` / `place_a` / `place_b` / `article_id` etc. reference rows in
this same city DB's `public` schema (Payload-owned: articles, places,
events). No foreign keys are declared against `public` — Payload manages
that schema's lifecycle independently (migrations, drafts, versioning) and
`engine` must survive `public` being dropped and rebuilt from a content
export, per ARCHITECTURE.md §1 rule 2. Referential integrity for these
columns is enforced by the API/worker layer, not the database.

`interactions` and `impressions` are the highest-volume tables in the
system and are RANGE-partitioned by `ts` (daily). Partitions are created by
`now_db.partitions.ensure_daily_partitions`, invoked automatically at the
end of `site:create` / `site:migrate` and intended to run daily via a
scheduled `now-db ensure-partitions` job (see package README — the schedule
itself is an infra concern, out of this package's scope).
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
        CREATE TABLE engine.entity_terms (
            entity_type  text NOT NULL,
            entity_id    uuid NOT NULL,
            term_id      uuid NOT NULL,  -- now_platform.engine.terms.id, no FK (cross-database)
            weight       numeric(5, 4) NOT NULL DEFAULT 1.0,
            source       text NOT NULL DEFAULT 'ai' CHECK (source IN ('ai', 'editor', 'inferred')),
            confidence   numeric(5, 4),
            created_at   timestamptz NOT NULL DEFAULT now(),
            PRIMARY KEY (entity_type, entity_id, term_id)
        )
        """
    )
    op.execute("CREATE INDEX ix_entity_terms_term ON engine.entity_terms (term_id)")

    op.execute(
        """
        CREATE TABLE engine.embeddings (
            entity_type  text NOT NULL,
            entity_id    uuid NOT NULL,
            model        text NOT NULL,
            vec          vector(1536) NOT NULL,
            updated_at   timestamptz NOT NULL DEFAULT now(),
            PRIMARY KEY (entity_type, entity_id, model)
        )
        """
    )
    # Single HNSW index across all entity_types. §7 "Row 3 similar" always
    # filters by entity_type before the kNN search, but `entity_type` is a
    # free-text column (not a fixed enum) so a migration-time partial index
    # per value isn't possible without hardcoding types here — which would
    # violate the "no site/type literals baked into engine" spirit of
    # §3.5. If a later wave finds recall/latency degrades as one
    # entity_type dominates the graph, split via a partial index per type
    # then (values are known at that point) rather than guessing now.
    op.execute(
        "CREATE INDEX ix_embeddings_hnsw ON engine.embeddings "
        "USING hnsw (vec vector_cosine_ops)"
    )

    op.execute(
        """
        CREATE TABLE engine.interactions (
            id           uuid NOT NULL DEFAULT gen_random_uuid(),
            anon_id      uuid NOT NULL,
            user_id      uuid,
            session_id   uuid NOT NULL,
            entity_type  text NOT NULL,
            entity_id    uuid NOT NULL,
            kind         text NOT NULL CHECK (
                             kind IN ('view', 'scroll', 'dwell', 'click', 'outbound',
                                      'search', 'exit', 'thumbs_down')
                         ),
            surface      text NOT NULL,
            rail         text,
            position     integer,
            dwell_ms     integer,
            scroll_pct   numeric(5, 2),
            referrer     text,
            utm          jsonb,
            device       text,
            ts           timestamptz NOT NULL DEFAULT now(),
            PRIMARY KEY (id, ts)
        ) PARTITION BY RANGE (ts)
        """
    )
    # Indexes on a partitioned parent propagate to every partition
    # automatically (PG >= 11) — no per-partition index maintenance needed.
    op.execute("CREATE INDEX ix_interactions_entity ON engine.interactions (entity_type, entity_id, ts DESC)")
    op.execute("CREATE INDEX ix_interactions_anon ON engine.interactions (anon_id, ts DESC)")
    op.execute("CREATE INDEX ix_interactions_session ON engine.interactions (session_id, ts DESC)")
    op.execute("CREATE INDEX ix_interactions_kind ON engine.interactions (kind, ts DESC)")

    op.execute(
        """
        CREATE TABLE engine.impressions (
            id          uuid NOT NULL DEFAULT gen_random_uuid(),
            session_id  uuid NOT NULL,
            anon_id     uuid NOT NULL,
            surface     text NOT NULL,
            rail        text,
            entity_id   uuid NOT NULL,
            position    integer,
            ts          timestamptz NOT NULL DEFAULT now(),
            PRIMARY KEY (id, ts)
        ) PARTITION BY RANGE (ts)
        """
    )
    op.execute("CREATE INDEX ix_impressions_entity ON engine.impressions (entity_id, ts DESC)")
    op.execute("CREATE INDEX ix_impressions_session ON engine.impressions (session_id, ts DESC)")
    op.execute("CREATE INDEX ix_impressions_rail ON engine.impressions (surface, rail, ts DESC)")

    op.execute(
        """
        CREATE TABLE engine.covisitation (
            entity_a     uuid NOT NULL,
            entity_b     uuid NOT NULL,
            score        numeric(8, 5) NOT NULL,
            "window"     text NOT NULL,  -- reserved word; must stay quoted everywhere it is referenced
            computed_at  timestamptz NOT NULL DEFAULT now(),
            PRIMARY KEY (entity_a, entity_b, "window")
        )
        """
    )
    op.execute('CREATE INDEX ix_covisitation_b ON engine.covisitation (entity_b, "window")')

    op.execute(
        """
        CREATE TABLE engine.travel_matrix (
            place_a      uuid NOT NULL,
            place_b      uuid NOT NULL,
            seconds      integer NOT NULL,
            meters       integer NOT NULL,
            mode         text NOT NULL DEFAULT 'drive',
            computed_at  timestamptz NOT NULL DEFAULT now(),
            PRIMARY KEY (place_a, place_b, mode)
        )
        """
    )
    op.execute("CREATE INDEX ix_travel_matrix_b ON engine.travel_matrix (place_b, mode)")

    op.execute(
        """
        CREATE TABLE engine.rail_cache (
            article_id   uuid NOT NULL,
            segment_id   text NOT NULL,
            rail         text NOT NULL,
            candidates   jsonb NOT NULL,
            rung         smallint NOT NULL DEFAULT 1,
            computed_at  timestamptz NOT NULL DEFAULT now(),
            PRIMARY KEY (article_id, segment_id, rail)
        )
        """
    )

    op.execute(
        """
        CREATE TABLE engine.quality_scores (
            entity_type  text NOT NULL,
            entity_id    uuid NOT NULL,
            score        numeric(6, 4) NOT NULL,
            components   jsonb,
            computed_at  timestamptz NOT NULL DEFAULT now(),
            PRIMARY KEY (entity_type, entity_id)
        )
        """
    )

    op.execute(
        """
        CREATE TABLE engine.type_relations (
            type          text PRIMARY KEY,
            exclude_same  boolean NOT NULL DEFAULT true,
            complements   text[] NOT NULL DEFAULT '{}'::text[],
            updated_at    timestamptz NOT NULL DEFAULT now()
        )
        """
    )
    # Seed the default matrix from ARCHITECTURE.md §4. Per-site overridable
    # in place (UPDATE engine.type_relations ...), no deploy required, and
    # every city starts from this baseline so the exclusion rule is never
    # accidentally absent for a freshly created site.
    op.execute(
        """
        INSERT INTO engine.type_relations (type, exclude_same, complements) VALUES
            ('stay',      true,  ARRAY['eat','drink','wellness','do']),
            ('eat',       true,  ARRAY['drink','do','event']),
            ('drink',     true,  ARRAY['eat','do']),
            ('wellness',  true,  ARRAY['eat','stay','do']),
            ('shop',      true,  ARRAY['eat','drink']),
            ('do',        false, ARRAY['eat','drink','stay']),
            ('event',     false, ARRAY['eat','drink','stay']),
            ('editorial', false, ARRAY['stay','eat','drink','wellness','shop','do','event'])
        """
    )

    # --- §8.G note -----------------------------------------------------
    # Partial indexes on (site_id, type, status) and a GiST index on `geo`
    # apply to `public.articles` / `public.places`, which belong to Payload
    # (E1.6) and do not exist yet at E0.2 baseline time — creating them here
    # would violate the public/engine ownership split and would fail outright
    # (no such tables). Add them in the migration that ships alongside/after
    # E1.6, once `public` is real. See this package's README "Notes for
    # later waves".


def downgrade() -> None:
    # Reverse dependency order. Safe pre-data; do not run against a live
    # city DB without a backup — see package README "Rollout notes".
    op.execute("DROP TABLE IF EXISTS engine.type_relations")
    op.execute("DROP TABLE IF EXISTS engine.quality_scores")
    op.execute("DROP TABLE IF EXISTS engine.rail_cache")
    op.execute("DROP TABLE IF EXISTS engine.travel_matrix")
    op.execute("DROP TABLE IF EXISTS engine.covisitation")
    op.execute("DROP TABLE IF EXISTS engine.impressions")
    op.execute("DROP TABLE IF EXISTS engine.interactions")
    op.execute("DROP TABLE IF EXISTS engine.embeddings")
    op.execute("DROP TABLE IF EXISTS engine.entity_terms")
