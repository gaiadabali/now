-- Decode the HTML entities the WordPress import stored literally.
--
--   psql -U now -d <city> -v ON_ERROR_STOP=1 -f decode-stored-entities.sql
--
-- 240 article titles across the two cities read `Catch &amp; Grill` rather
-- than `Catch & Grill`, and one author is `Something &amp; Co`. The reader
-- site has decoded these at render since the entity-decoding commit, so the
-- public pages have been correct — but the TEAM EDITOR shows what is stored,
-- so an editor sees the raw entity, and anything that sorts, searches or
-- exports the title sees it too. Decoding at render fixed the symptom on one
-- surface; this fixes the data.
--
-- WHAT IS ACTUALLY IN THERE. Exactly two entities, confirmed by pulling the
-- distinct matches rather than assuming: `&amp;` and `&nbsp;`. No numeric
-- entities, no smart quotes, nothing else. So this is a narrow, checkable
-- substitution and not a general HTML-entity decoder pretending to be one.
--
-- DECODED ONCE, NOT TO A FIXED POINT. `&amp;amp;` is how an author writes a
-- visible `&amp;`, and decoding twice would silently turn it into `&`. The
-- two substitutions below are sequential, which is only equivalent to a
-- single pass because neither entity's expansion can form the other — and
-- because no row contains `&amp;amp;` or `&amp;nbsp;`. Verified before
-- running; the guard at the bottom re-checks it rather than trusting me.
--
-- `&nbsp;` becomes U+00A0, matching `decodeEntities` in the reader app's
-- lib/html.ts. A plain space would read the same on screen and quietly
-- change the text.
--
-- BOTH COPIES. An article's title lives in `articles.title` AND in
-- `_articles_v.version_title`, and the admin list reads the version. Fixing
-- only the first would leave the editor showing the entity it was meant to
-- remove.

BEGIN;

-- Refuse to run if a double-encoded entity is present: the sequential
-- substitution below would decode it twice and lose an author's literal
-- `&amp;`. Nothing in either city has one today.
DO $$
DECLARE offenders bigint;
BEGIN
    SELECT (SELECT count(*) FROM public.articles
             WHERE title LIKE '%&amp;amp;%' OR title LIKE '%&amp;nbsp;%')
         + (SELECT count(*) FROM public.authors
             WHERE name LIKE '%&amp;amp;%' OR name LIKE '%&amp;nbsp;%')
      INTO offenders;
    IF offenders > 0 THEN
        RAISE EXCEPTION
            'refusing to run: % row(s) contain a double-encoded entity, which this would decode twice',
            offenders;
    END IF;
END $$;

UPDATE public.articles
   SET title = replace(replace(title, '&amp;', '&'), '&nbsp;', U&'\00A0')
 WHERE title LIKE '%&amp;%' OR title LIKE '%&nbsp;%';

UPDATE public._articles_v
   SET version_title = replace(replace(version_title, '&amp;', '&'), '&nbsp;', U&'\00A0')
 WHERE version_title LIKE '%&amp;%' OR version_title LIKE '%&nbsp;%';

UPDATE public.authors
   SET name = replace(replace(name, '&amp;', '&'), '&nbsp;', U&'\00A0')
 WHERE name LIKE '%&amp;%' OR name LIKE '%&nbsp;%';

COMMIT;

-- Both copies of the title must agree, or the editor and the reader site
-- disagree about what an article is called.
SELECT
    (SELECT count(*) FROM public.articles
      WHERE title LIKE '%&amp;%' OR title LIKE '%&nbsp;%')            AS articles_remaining,
    (SELECT count(*) FROM public._articles_v
      WHERE version_title LIKE '%&amp;%' OR version_title LIKE '%&nbsp;%')
                                                                      AS versions_remaining,
    (SELECT count(*) FROM public.authors
      WHERE name LIKE '%&amp;%' OR name LIKE '%&nbsp;%')              AS authors_remaining,
    (SELECT count(*) FROM public._articles_v v JOIN public.articles a ON a.id = v.parent_id
      WHERE v.version_title IS DISTINCT FROM a.title)                 AS title_mismatches;
