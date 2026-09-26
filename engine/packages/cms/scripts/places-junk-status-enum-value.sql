-- Apply `20260926_090000_places_junk_status_enum_value` on a host that
-- cannot run the migration (docs/DEPLOY.md — the runner image carries
-- `src/migrations/` but no Payload module to execute them with).
--
--   docker exec now-postgres psql -U now -d <city> -v ON_ERROR_STOP=1 \
--     -f /tmp/places-junk-status-enum-value.sql
--
-- ORDER MATTERS. Run this BEFORE `places-provenance-and-curation-fields.sql`
-- and BEFORE rolling any image whose place desk (P1.6) writes
-- `status = 'junk'`. Additive only — no existing row's `status` changes.
--
-- Copied verbatim from the migration's `up()` (itself plain SQL), same
-- "transcription, not reimplementation" guarantee `articles-slug.sql`
-- documents.

BEGIN;

ALTER TYPE "public"."enum_places_status" ADD VALUE IF NOT EXISTS 'junk';
ALTER TYPE "public"."enum__places_v_version_status" ADD VALUE IF NOT EXISTS 'junk';

INSERT INTO payload_migrations (name, batch)
VALUES ('20260926_090000_places_junk_status_enum_value', (SELECT COALESCE(MAX(batch), 0) + 1 FROM payload_migrations));

COMMIT;

-- Verify: the label exists and nothing has used it yet.
--
--   SELECT enumlabel FROM pg_enum
--     WHERE enumtypid = 'public.enum_places_status'::regtype ORDER BY enumsortorder;
--   -- expect: active, closed, pending_review, junk
--
--   SELECT count(*) FROM public.places WHERE status = 'junk';  -- expect 0
