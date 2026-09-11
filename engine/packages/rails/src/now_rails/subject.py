"""Resolves the `article_id` in `GET /v1/{site}/articles/{id}/rails` into
everything the three rails need about it: its own L1 type (competitor
exclusion, all three rails), and -- for Row 1/Row 2, which recommend
*places* -- the geo/price/vibe context of whichever place this article is
actually about.

**Why a place at all, from an article subject.** `public.articles` carries
no `lat`/`lng`/`area_term`/`price_band` of its own (verified against the
real schema -- `engine/packages/cms` migration) -- an article's location
lives one hop away, through `public.place_mentions`. This module picks the
single most-authoritative mention (`role='featured'` > `'reviewed'` >
`'mentioned'`, the CMS's own ordering of how central a place is to a
piece) as the article's "subject place" for Row 1/2's geo/price/vibe
inputs. An article with no place mention at all (real data today: **0 of
4,772** -- `place_mentions` is empty archive-wide, verified directly) has
`place=None`; Row 1/2 degrade accordingly (see those modules).

**F50 synthetic overlay.** `articles.primary_type` is NULL for all 4,772
real rows. `synthetic_type_overlay=True` assigns a deterministic type from
the same pool `public.places.type` draws from (`now_filters.synthetic
.deterministic_type`, imported rather than re-implemented -- both
`articles.primary_type` and `places.type` are the identical
`engine.type_relations`-keyed L1 taxonomy, ARCHITECTURE.md Sec.4, so this
is the *same* pool the same way `now_blender.reranker._to_candidate`
reuses `now_blender.synthetic.deterministic_format` for the sibling
`format` column -- not a second hash scheme). Never applied unless the
caller asks: the honest, real value (`None`) is always what a
non-synthetic caller sees.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from now_filters.models import Candidate
from now_filters.synthetic import VENUE_TYPES, deterministic_type
from sqlalchemy import text
from sqlalchemy.engine import Connection

# Higher priority first -- the CMS's own ordering of how central a place
# mention is to the piece (`enum_place_mentions_role`: mentioned/featured/
# reviewed). A hero-review article should use the reviewed venue as its
# geo/price/vibe subject, not an incidentally name-dropped one.
_ROLE_PRIORITY_SQL = "CASE m.role WHEN 'featured' THEN 0 WHEN 'reviewed' THEN 1 ELSE 2 END"

# One round trip, not two: article + its single best place mention (if
# any) via a LEFT JOIN LATERAL picking the top-priority mention. Every
# p95-ms saved here is one less round trip on the cold path -- see the
# package README's timing section for why round-trip COUNT, not query
# complexity, is this rail's real cost driver on this dev box (Postgres
# in Docker, ~12-15ms/round trip, measured).
_ARTICLE_WITH_SUBJECT_PLACE_SQL = text(
    f"""
    SELECT a.id, a.primary_type::text AS primary_type, a.format::text AS format,
           a.series_key, a.published_at, a.title, a._status,
           p.id AS place_id, p.type::text AS place_type, p.subtype::text AS place_subtype,
           p.status::text AS place_status, p.area_term::text AS place_area_term, p.org_id AS place_org_id,
           p.price_band::text AS place_price_band, p.lat::float8 AS place_lat, p.lng::float8 AS place_lng
      FROM public.articles a
      LEFT JOIN LATERAL (
          SELECT m.place_id, m.role
            FROM public.place_mentions m
           WHERE m.article_id = a.id
           ORDER BY {_ROLE_PRIORITY_SQL}, m.id
           LIMIT 1
      ) best_mention ON true
      LEFT JOIN public.places p ON p.id = best_mention.place_id
     WHERE a.id = :id
    """
)


@dataclass(frozen=True)
class ArticleSubject:
    article_id: int
    primary_type: str | None
    format: str | None
    series_key: str | None
    published_at: datetime | None
    title: str | None
    status: str
    place: Candidate | None  # the article's subject place, if any -- see module docstring
    primary_type_is_synthetic: bool = False


def fetch_article_subject(
    conn: Connection, article_id: int, *, synthetic_type_overlay: bool = False
) -> ArticleSubject | None:
    """`None` if `article_id` doesn't exist or isn't published -- callers
    map that to a 404, exactly like `now_search.engine.SearchEngine
    .fetch_summaries` does for an unknown id (a missing key, not a raised
    exception, is this package's own convention for "no such row" -- see
    e.g. `now_blender.quality.fetch_quality`'s docstring)."""
    row = conn.execute(_ARTICLE_WITH_SUBJECT_PLACE_SQL, {"id": article_id}).first()
    if row is None or row._status != "published":
        return None

    primary_type = row.primary_type
    is_synthetic = False
    if primary_type is None and synthetic_type_overlay:
        primary_type = deterministic_type(article_id, pool=VENUE_TYPES)
        is_synthetic = True

    place: Candidate | None = None
    if row.place_id is not None:
        place = Candidate(
            entity_type="place",
            entity_id=row.place_id,
            type=row.place_type,
            subtype=row.place_subtype,
            status=row.place_status,
            area_term=row.place_area_term,
            org_id=row.place_org_id,
            price_band=row.place_price_band,
            lat=row.place_lat,
            lng=row.place_lng,
        )

    return ArticleSubject(
        article_id=row.id,
        primary_type=primary_type,
        format=row.format,
        series_key=row.series_key,
        published_at=row.published_at,
        title=row.title,
        status=row._status,
        place=place,
        primary_type_is_synthetic=is_synthetic,
    )
