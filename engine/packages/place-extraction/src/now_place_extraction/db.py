"""Postgres access for the city DB. Same connection convention as
now-quality/now-embeddings (`now_db.settings.city_database_url`).

No schema change of any kind was needed for this ticket -- `public.places`
and `public.place_mentions` already carry every column this pipeline
needs (verified live against both cities before writing any code). Idempotency
is therefore enforced in APPLICATION code, not via `ON CONFLICT`:

  - `places`: matched by `slug` (the table's one unique, non-id key) before
    ever inserting -- a second run that re-derives the same candidate
    reuses the existing row's id rather than creating a duplicate.
  - `place_mentions`: matched by (article_id, place_id, surface_text)
    before inserting -- there is no unique constraint to hang an
    `ON CONFLICT` off, so this is a SELECT-then-INSERT-if-absent, safe
    under this pipeline's own single-writer-per-run usage.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from now_db.settings import city_database_url
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine


def make_engine(db_ref: str) -> Engine:
    return create_engine(city_database_url(db_ref))


# ---------------------------------------------------------------- articles

@dataclass
class ArticleRecord:
    id: int
    title: str
    body_blocks: list | None


_FETCH_ARTICLES_SQL = text(
    """
    select id, title, body_blocks
    from public.articles
    order by id
    """
)


def fetch_articles(engine: Engine, *, limit: int | None = None) -> list[ArticleRecord]:
    sql = _FETCH_ARTICLES_SQL
    params: dict = {}
    if limit is not None:
        sql = text(str(_FETCH_ARTICLES_SQL) + " limit :limit")
        params = {"limit": limit}
    with engine.connect() as conn:
        rows = conn.execute(sql, params).mappings().all()
    return [ArticleRecord(id=r["id"], title=r["title"] or "", body_blocks=r["body_blocks"]) for r in rows]


# ------------------------------------------------------------------ places

@dataclass
class PlaceRow:
    id: int
    name: str
    slug: str
    org_id: str | None
    status: str


_FETCH_PLACES_SQL = text("select id, name, slug, org_id, status from public.places order by id")


def fetch_places(engine: Engine) -> list[PlaceRow]:
    with engine.connect() as conn:
        rows = conn.execute(_FETCH_PLACES_SQL).mappings().all()
    return [PlaceRow(id=r["id"], name=r["name"], slug=r["slug"], org_id=r["org_id"], status=r["status"]) for r in rows]


_SLUG_PUNCT_RE = re.compile(r"[^a-z0-9]+")


def slugify(name: str) -> str:
    folded = unicodedata.normalize("NFKD", name)
    folded = "".join(c for c in folded if not unicodedata.combining(c))
    folded = folded.lower()
    folded = _SLUG_PUNCT_RE.sub("-", folded).strip("-")
    return folded or "place"


_FIND_BY_SLUG_SQL = text("select id from public.places where slug = :slug")

# `type`/`subtype`/`status` follow the EXACT placeholder convention the
# E1.8 loader already established for "not yet classified by E2.1" (see
# README.md and PROGRESS.md F27) -- `editorial`/`city-guide`/
# `pending_review`. This is not a new sentinel invented here: it is the
# same value already sitting on all 177 pre-existing rows, and it is
# deliberately NOT the newer `unknown` type sentinel (F49), because
# `unknown` has no matching `subtype` value in the enum today (verified
# live) -- inserting `type='unknown'` would need a `subtype` this schema
# cannot express yet. Reclassifying either placeholder to something more
# specific is E2.1's job, not this ticket's (E2.3 extracts and dedups
# entities; it does not classify them) -- flagged as a follow-up in the
# final report, not silently done here.
_INSERT_PLACE_SQL = text(
    """
    insert into public.places (name, slug, type, subtype, status)
    values (:name, :slug, 'editorial', 'city-guide', 'pending_review')
    returning id
    """
)


def find_or_create_place(engine: Engine, *, name: str, preferred_slug: str) -> tuple[int, bool]:
    """Returns (place_id, created). Slug collisions are resolved by
    numeric suffix, mirroring Payload's own `-2`/`-3` convention visible
    on the existing 177 rows, so a human skimming `public.places` sees one
    consistent pattern regardless of which pipeline created a row."""
    with engine.begin() as conn:
        existing = conn.execute(_FIND_BY_SLUG_SQL, {"slug": preferred_slug}).scalar()
        if existing is not None:
            return int(existing), False

        slug = preferred_slug
        suffix = 2
        while True:
            row = conn.execute(_FIND_BY_SLUG_SQL, {"slug": slug}).scalar()
            if row is None:
                break
            slug = f"{preferred_slug}-{suffix}"
            suffix += 1

        new_id = conn.execute(_INSERT_PLACE_SQL, {"name": name, "slug": slug}).scalar()
        return int(new_id), True


# ------------------------------------------------------------- mentions

_FIND_MENTION_SQL = text(
    """
    select id from public.place_mentions
    where article_id = :article_id and place_id = :place_id and surface_text = :surface_text
    """
)

_INSERT_MENTION_SQL = text(
    """
    insert into public.place_mentions (article_id, place_id, "offset", surface_text, role)
    values (:article_id, :place_id, :offset, :surface_text, :role)
    """
)


def upsert_mention(
    engine: Engine,
    *,
    article_id: int,
    place_id: int,
    offset: int,
    surface_text: str,
    role: str = "mentioned",
) -> bool:
    """Returns True if a new row was inserted, False if an identical
    mention already existed (idempotent re-run)."""
    with engine.begin() as conn:
        existing = conn.execute(
            _FIND_MENTION_SQL,
            {"article_id": article_id, "place_id": place_id, "surface_text": surface_text},
        ).scalar()
        if existing is not None:
            return False
        conn.execute(
            _INSERT_MENTION_SQL,
            {
                "article_id": article_id,
                "place_id": place_id,
                "offset": offset,
                "surface_text": surface_text,
                "role": role,
            },
        )
        return True
