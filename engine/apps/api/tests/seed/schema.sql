-- Minimal `engine.sites` table for testing engine-api against a throwaway
-- Postgres instance. This mirrors -- as closely as a hand-written test seed
-- reasonably should -- the column shape and schema placement fixed by the
-- schema agent (E0.2): see
-- engine/packages/platform-db/src/now_platform_db/migrations/versions/0001_baseline_engine_schema.py
-- ("CREATE TABLE engine.sites (...)"). This is NOT a migration and must
-- never be applied to a real environment -- the real baseline lives in
-- engine/packages/platform-db/, owned by senior-db.
CREATE SCHEMA IF NOT EXISTS engine;

CREATE TABLE IF NOT EXISTS engine.sites (
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
    CONSTRAINT uq_sites_slug UNIQUE (slug),
    CONSTRAINT uq_sites_hostname UNIQUE (hostname),
    CONSTRAINT uq_sites_db_ref UNIQUE (db_ref)
);
