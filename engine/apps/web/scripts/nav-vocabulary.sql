-- The reader nav, in the magazine's own vocabulary (S6).
--
--   docker exec now-postgres psql -U now -d now_platform -v ON_ERROR_STOP=1 \
--     -f /tmp/nav-vocabulary.sql
--
-- WHY THIS IS SQL AND NOT A CODE CHANGE. `site.nav` has been a registry read
-- since S1.3: `getSiteConfig()` takes it from `engine.sites.nav` with the baked
-- config file as the floor. So renaming a section is data, it reaches readers
-- within the 30-second TTL, and it needs no deploy. This file exists only so
-- the same decision can be applied to each environment identically and
-- reviewed before it is; the console at /team-editor/platform/sites/<slug>
-- does the same thing through a form, and is where the next change should be
-- made.
--
-- WHAT CHANGED, AND WHAT DELIBERATELY DID NOT.
-- The approved comps show the live magazine's own words: News, Events,
-- Features, Hotels, Resto & Bars, Wellness, Guides, Explore, Offers. Only the
-- ones with somewhere to point are here.
--
--   Dining        -> Resto & Bars   /dining         renamed
--   Stay          -> Hotels         /stay           renamed
--   (new)            Explore        /areas          the neighbourhood index
--   Wellness, Things to Do, Events, Guides          unchanged
--
-- News, Features and Offers are NOT added. There is no `/news`, `/features` or
-- `/offers` route: the router resolves a section slug against SECTION_MAP
-- (dining, stay, wellness, things-to-do, events, guides, editorial,
-- unclassified) plus the static pages, and anything else falls through to an
-- article lookup and 404s. Putting them in the nav would be six words that
-- look like navigation and behave like a dead end -- the exact defect S2
-- removed when `/latest` and four guide cards were found 404ing from the home
-- page, and the one `scripts/smoke.sh`'s link crawl now fails the build over.
-- They become nav entries when they become routes, and not before.
--
-- Hotels is the one that was actually missing rather than mislabelled: 453
-- published stay stories in Bali and 420 in Jakarta had no entry of their own,
-- while the competitor runs Stay and Hotel News as two separate sections.

BEGIN;

UPDATE engine.sites
   SET nav = '[
         {"label": "Resto & Bars",  "href": "/dining"},
         {"label": "Hotels",        "href": "/stay"},
         {"label": "Wellness",      "href": "/wellness"},
         {"label": "Things to Do",  "href": "/things-to-do"},
         {"label": "Events",        "href": "/events"},
         {"label": "Guides",        "href": "/guides"},
         {"label": "Explore",       "href": "/areas"}
       ]'::jsonb,
       updated_at = now()
 WHERE slug IN ('jakarta', 'bali')
   AND status <> 'disabled';

COMMIT;

-- Verify: every row should report 7 items and jsonb_typeof = array. A row
-- reading `object` is still ungoverned and falling back to its config file.
--
--   SELECT slug, jsonb_typeof(nav) AS shape,
--          jsonb_array_length(nav) AS items,
--          jsonb_path_query_array(nav, '$[*].label') AS labels
--     FROM engine.sites ORDER BY slug;
