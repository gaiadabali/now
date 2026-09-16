-- Backfill `_articles_v` so the archive is visible in the team editor.
--
--   psql -U now -d <city> -v ON_ERROR_STOP=1 -f backfill-article-versions.sql
--
-- The SQL twin of `backfill-article-versions.mjs`, for hosts that carry no
-- Node toolchain. The deployment box runs images only and has no checkout
-- (docs/DEPLOY.md), so `payload run` is not available there and the same
-- work has to be expressible as a statement `docker exec now-postgres psql`
-- can take.
--
-- WHY A SECOND IMPLEMENTATION IS SAFE HERE, WHEN IT USUALLY IS NOT.
-- `db.createVersion` earns its keep when a collection has child tables —
-- blocks, arrays and relationships each land in their own `_x_v_*` table and
-- reproducing that mapping by hand is how people corrupt a database. This
-- collection has none: `_articles_v` is the only versions table, `articles`
-- is the only parent table, and `body_blocks` is a single jsonb column. The
-- mapping is `articles.<col>` -> `_articles_v.version_<col>` for all fifteen
-- content columns, `articles.id` -> `parent_id`, and nothing else. Checked
-- against information_schema rather than assumed.
--
-- It was also validated the other way round: the rows this produces were
-- diffed, column by column, against rows `db.createVersion` had already
-- written for the same articles, and they agree on every one.
--
-- Idempotent. A parent that already has a version row is skipped, because it
-- may carry a genuine draft this has no business overwriting.
--
-- Read-only rehearsal — run this first, it writes nothing:
--
--   SELECT count(*) AS would_create FROM public.articles a
--    WHERE NOT EXISTS (SELECT 1 FROM public._articles_v v WHERE v.parent_id = a.id);

BEGIN;

INSERT INTO public._articles_v (
    parent_id,
    version_kind,
    version_title,
    version_dek,
    version_body_blocks,
    version_hero_media_id,
    version_author_id,
    version_primary_type,
    version_format,
    version_published_at,
    version_legacy_wp_id,
    version_legacy_permalink,
    version_series_key,
    version_updated_at,
    version_created_at,
    version__status,
    created_at,
    updated_at,
    latest,
    autosave
)
SELECT
    a.id,
    a.kind::text::enum__articles_v_version_kind,
    a.title,
    a.dek,
    a.body_blocks,
    a.hero_media_id,
    a.author_id,
    a.primary_type::text::enum__articles_v_version_primary_type,
    a.format::text::enum__articles_v_version_format,
    a.published_at,
    a.legacy_wp_id,
    a.legacy_permalink,
    a.series_key,
    -- The snapshot carries the article's OWN timestamps, not now(). The row's
    -- created_at/updated_at below carry the same values: a version row holds
    -- two pairs, and leaving the snapshot's pair null blanks Last Modified on
    -- every article in the list view, which reads the snapshot.
    a.updated_at,
    a.created_at,
    -- COALESCE because `_status` is nullable on rows that predate drafts
    -- being enabled; an article with no status is a published one.
    COALESCE(a._status::text, 'published')::enum__articles_v_version_status,
    a.created_at,
    a.updated_at,
    TRUE,
    FALSE
FROM public.articles a
WHERE NOT EXISTS (
    SELECT 1 FROM public._articles_v v WHERE v.parent_id = a.id
);

-- Belt and braces: the admin resolves one row per parent by `latest`, so two
-- would show the article twice. Nothing above can produce that — the INSERT
-- skips parents that already have a row — but asserting it costs nothing and
-- the alternative is discovering it in the UI.
DO $$
DECLARE dupes bigint;
BEGIN
    SELECT count(*) INTO dupes FROM (
        SELECT parent_id FROM public._articles_v
         WHERE latest AND parent_id IS NOT NULL
         GROUP BY parent_id HAVING count(*) > 1
    ) x;
    IF dupes > 0 THEN
        RAISE EXCEPTION 'refusing to commit: % parent(s) now have more than one latest version', dupes;
    END IF;
END $$;

COMMIT;

-- What the admin will now see.
SELECT
    (SELECT count(*) FROM public.articles)                                AS articles,
    (SELECT count(*) FROM public._articles_v WHERE latest)                AS latest_versions,
    (SELECT count(*) FROM public._articles_v WHERE parent_id IS NULL)     AS orphan_rows;
