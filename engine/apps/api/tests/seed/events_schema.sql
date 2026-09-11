-- Minimal `engine.interactions` / `engine.impressions` mirror for
-- events-endpoint tests (E0.5 + E0.7 + F66), run against a city database
-- (now_alpha, now_beta, ...) in the same throwaway Postgres container
-- tests/seed/schema.sql seeds the platform registry into -- see
-- engine/apps/api/README.md "Testing".
--
-- Matches engine/packages/db/src/now_db/migrations/versions/0001 + 0002 +
-- 0003 + 0007 exactly for these two tables -- 0003 (decision C4) makes
-- `interactions.entity_id` nullable and adds `target_url`; 0007 (F66)
-- widens both tables' `entity_id` from `uuid` to `text` so a real
-- `public.articles.id`/`public.places.id` (a Payload integer serial, never
-- a uuid) can be stored verbatim. `embeddings`/`entity_terms`/etc. are
-- deliberately omitted: not needed by these tests, and 0001's
-- `vector`/`postgis` extensions aren't installed on the plain
-- `postgres:16` image these tests run against. NOT a migration -- the real
-- baseline lives in engine/packages/db/, owned by senior-db; this file
-- must be kept in sync with it by hand, same as tests/seed/schema.sql
-- already is for `sites`.
CREATE SCHEMA IF NOT EXISTS engine;

CREATE TABLE IF NOT EXISTS engine.interactions (
    id           uuid NOT NULL DEFAULT gen_random_uuid(),
    anon_id      uuid NOT NULL,
    user_id      uuid,
    session_id   uuid NOT NULL,
    entity_type  text NOT NULL,
    entity_id    text,
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
    query        text,
    target_url   text,
    PRIMARY KEY (id, ts)
) PARTITION BY RANGE (ts);

CREATE TABLE IF NOT EXISTS engine.impressions (
    id          uuid NOT NULL DEFAULT gen_random_uuid(),
    session_id  uuid NOT NULL,
    anon_id     uuid NOT NULL,
    surface     text NOT NULL,
    rail        text,
    entity_id   text NOT NULL,
    position    integer,
    ts          timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (id, ts)
) PARTITION BY RANGE (ts);

-- Daily partitions for [today-3, today+3]. Comfortably wraps any
-- reasonably-clocked test event while deliberately leaving a *clearly*
-- out-of-range ts (e.g. the year 2000) with no partition to land in --
-- that gap is exactly what test_events.py's out-of-range test exercises
-- (must come back as 400, never a raw 500).
DO $$
DECLARE
    d date;
BEGIN
    FOR d IN SELECT generate_series(CURRENT_DATE - 3, CURRENT_DATE + 3, interval '1 day')::date LOOP
        EXECUTE format(
            'CREATE TABLE IF NOT EXISTS engine.interactions_p%s PARTITION OF engine.interactions FOR VALUES FROM (%L) TO (%L)',
            to_char(d, 'YYYY_MM_DD'), d, d + 1
        );
        EXECUTE format(
            'CREATE TABLE IF NOT EXISTS engine.impressions_p%s PARTITION OF engine.impressions FOR VALUES FROM (%L) TO (%L)',
            to_char(d, 'YYYY_MM_DD'), d, d + 1
        );
    END LOOP;
END $$;
