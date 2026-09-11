"""Test-only helper: stands up the minimal, faithful SUBSET of the Payload
`public` schema (`articles`, `classification_reviews` +
`classification_reviews_rels`, the F86 no-clobber trigger) that
`apply_llm_labels.py`'s integration tests need, against `now_test`.

`now_test` (verified live before writing this) carries ONLY the
alembic-owned `engine` schema (created by `now-db create`/`now-db migrate`)
-- it has no `public.articles`/`classification_reviews` at all, because
those are Payload/drizzle-owned tables normally created by the CMS
package's own migration runner (node/Next.js), which this Python test
suite has no reason to boot. Rather than skip real integration coverage of
the F86 interaction and the `public.articles` guard, this module recreates
that subset DIRECTLY FROM THE CANONICAL DDL TEXT in
`engine/packages/cms/src/migrations/20260908_131927_initial_schema.ts`,
`.../20260910_020207_add_classification_reviews.ts` and
`.../20260910_060000_classification_reviews_no_clobber_trigger.ts` -- copied
verbatim for the columns/enums/trigger this suite touches, with
unrelated FKs (media, authors, users, places) omitted since nothing here
exercises them. This is NOT a new migration and does not touch
`engine/packages/db/migrations/` or `engine/packages/cms/src/migrations/`
-- it is scaffolding for a test fixture only, created and dropped by the
same pytest fixture, every run, so `now_test` is left exactly as found.
"""
from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.engine import Engine

_DDL_UP = """
DROP TABLE IF EXISTS classification_reviews_rels CASCADE;
DROP TABLE IF EXISTS classification_reviews CASCADE;
DROP TABLE IF EXISTS articles CASCADE;
DROP TYPE IF EXISTS enum_articles_primary_type CASCADE;
DROP TYPE IF EXISTS enum_articles_format CASCADE;
DROP TYPE IF EXISTS enum_classification_reviews_entity_type CASCADE;
DROP TYPE IF EXISTS enum_classification_reviews_facet_key CASCADE;
DROP TYPE IF EXISTS enum_classification_reviews_confidence_band CASCADE;
DROP TYPE IF EXISTS enum_classification_reviews_source CASCADE;
DROP TYPE IF EXISTS enum_classification_reviews_review_state CASCADE;
DROP FUNCTION IF EXISTS public.classification_reviews_protect_human_decision() CASCADE;

CREATE TYPE enum_articles_primary_type AS ENUM
  ('do', 'drink', 'eat', 'editorial', 'event', 'shop', 'stay', 'wellness', 'unknown');
CREATE TYPE enum_articles_format AS ENUM
  ('city-guide', 'event', 'feature', 'guide', 'heritage', 'listing', 'news', 'offer', 'opinion', 'people', 'review');

CREATE TABLE articles (
    id             serial PRIMARY KEY NOT NULL,
    title          varchar,
    primary_type   enum_articles_primary_type,
    format         enum_articles_format,
    legacy_wp_id   numeric,
    updated_at     timestamp(3) with time zone DEFAULT now() NOT NULL,
    created_at     timestamp(3) with time zone DEFAULT now() NOT NULL
);
CREATE UNIQUE INDEX articles_legacy_wp_id_idx ON articles USING btree (legacy_wp_id);

CREATE TYPE enum_classification_reviews_entity_type AS ENUM ('article', 'place');
CREATE TYPE enum_classification_reviews_facet_key AS ENUM ('type', 'subtype', 'format', 'location');
CREATE TYPE enum_classification_reviews_confidence_band AS ENUM ('low', 'medium', 'high');
CREATE TYPE enum_classification_reviews_source AS ENUM ('ai', 'editor', 'inferred');
CREATE TYPE enum_classification_reviews_review_state AS ENUM ('pending', 'accepted', 'corrected', 'unclassifiable');

CREATE TABLE classification_reviews (
    id               serial PRIMARY KEY NOT NULL,
    entity_type      enum_classification_reviews_entity_type,
    legacy_category  varchar,
    facet_key        enum_classification_reviews_facet_key NOT NULL,
    term_id          varchar,
    proposed_value   varchar NOT NULL,
    confidence       numeric NOT NULL,
    confidence_band  enum_classification_reviews_confidence_band,
    reasoning        varchar NOT NULL,
    source           enum_classification_reviews_source DEFAULT 'ai',
    weight           numeric DEFAULT 1,
    review_state     enum_classification_reviews_review_state DEFAULT 'pending' NOT NULL,
    final_value      varchar,
    reviewed_by_id   integer,
    reviewed_at      timestamp(3) with time zone,
    site_slug        varchar,
    updated_at       timestamp(3) with time zone DEFAULT now() NOT NULL,
    created_at       timestamp(3) with time zone DEFAULT now() NOT NULL
);

CREATE TABLE classification_reviews_rels (
    id           serial PRIMARY KEY NOT NULL,
    "order"      integer,
    parent_id    integer NOT NULL,
    path         varchar NOT NULL,
    articles_id  integer,
    places_id    integer
);
ALTER TABLE classification_reviews_rels
    ADD CONSTRAINT classification_reviews_rels_parent_fk
    FOREIGN KEY (parent_id) REFERENCES classification_reviews(id) ON DELETE CASCADE;
ALTER TABLE classification_reviews_rels
    ADD CONSTRAINT classification_reviews_rels_articles_fk
    FOREIGN KEY (articles_id) REFERENCES articles(id) ON DELETE CASCADE;

-- F86 (migration 20260910_060000), verbatim.
CREATE OR REPLACE FUNCTION public.classification_reviews_protect_human_decision()
RETURNS trigger
LANGUAGE plpgsql
AS $fn$
BEGIN
  IF OLD.source = 'editor'
     AND OLD.review_state <> 'pending'
     AND NEW.source IS DISTINCT FROM 'editor'
  THEN
    RAISE EXCEPTION
      'classification_reviews id=%: this row was already decided by a human (review_state=%, source=editor) -- an automated writer (source=%) may not overwrite that decision. Only a write that itself asserts source=''editor'' may modify a decided row. (F86)',
      OLD.id, OLD.review_state, NEW.source
      USING ERRCODE = 'restrict_violation';
  END IF;
  RETURN NEW;
END;
$fn$;

CREATE TRIGGER classification_reviews_no_clobber
  BEFORE UPDATE ON public.classification_reviews
  FOR EACH ROW
  EXECUTE FUNCTION public.classification_reviews_protect_human_decision();
"""

_DDL_DOWN = """
DROP TABLE IF EXISTS classification_reviews_rels CASCADE;
DROP TABLE IF EXISTS classification_reviews CASCADE;
DROP TABLE IF EXISTS articles CASCADE;
DROP TYPE IF EXISTS enum_articles_primary_type CASCADE;
DROP TYPE IF EXISTS enum_articles_format CASCADE;
DROP TYPE IF EXISTS enum_classification_reviews_entity_type CASCADE;
DROP TYPE IF EXISTS enum_classification_reviews_facet_key CASCADE;
DROP TYPE IF EXISTS enum_classification_reviews_confidence_band CASCADE;
DROP TYPE IF EXISTS enum_classification_reviews_source CASCADE;
DROP TYPE IF EXISTS enum_classification_reviews_review_state CASCADE;
DROP FUNCTION IF EXISTS public.classification_reviews_protect_human_decision() CASCADE;
"""


def create_scratch_public_schema(engine: Engine) -> None:
    with engine.begin() as conn:
        for stmt in _DDL_UP.split(";\n\n"):
            stmt = stmt.strip()
            if stmt:
                conn.execute(text(stmt))


def drop_scratch_public_schema(engine: Engine) -> None:
    with engine.begin() as conn:
        for stmt in _DDL_DOWN.strip().split(";\n"):
            stmt = stmt.strip().rstrip(";")
            if stmt:
                conn.execute(text(stmt))


def wipe_engine_entity_terms_for_test_entities(engine: Engine, entity_ids: list[str]) -> None:
    """Belt-and-braces cleanup for `engine.entity_terms` test rows this
    suite inserted directly (bypassing the classifier's own write path) --
    keeps `now_test` leaving no fixtures behind (per this ticket's brief)."""
    if not entity_ids:
        return
    with engine.begin() as conn:
        conn.execute(
            text("delete from engine.entity_terms where entity_type = 'article' and entity_id = any(:ids)"),
            {"ids": entity_ids},
        )
