"""Postgres access for the city databases (and one read of the platform's
partnerships). Same connection convention as the other engine CLIs:
`now_db.settings.city_database_url(<db name or DSN>)`.

READS are plain SQL. The only WRITES in this package are:

  * `triage --apply`  -- `status = 'junk'` on pending rows (and its revert);
  * `rank --apply`    -- `quality_score`;
  * `dedupe --apply` / `merge` / `unmerge` -- see merge.py.

Every write path takes an explicit `Connection` so the caller owns the
transaction (one per merge, one per apply), and tests can wrap a whole run
in a transaction they roll back.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from now_db.settings import city_database_url
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection, Engine

CITY_DB = {"jakarta": "now_jakarta", "bali": "now_bali"}


def make_engine(db_ref: str) -> Engine:
    return create_engine(city_database_url(db_ref))


@dataclass
class PlaceEvidence:
    id: int
    name: str
    slug: str
    status: str
    source: str | None
    type: str | None
    address: str | None
    area_term: str | None
    org_id: str | None
    google_place_id: str | None
    legacy_wp_id: int | None
    merged_into_id: int | None
    aliases: list | None
    featured: int = 0
    mentions: int = 0
    articles: int = 0
    newest: datetime | None = None
    partnered: bool = False
    # filled by triage
    flags: dict = field(default_factory=dict)


_EVIDENCE_SQL = text(
    """
    select p.id, p.name, p.slug, p.status::text as status, p.source::text as source,
           p.type::text as type, p.address, p.area_term::text as area_term,
           p.org_id::text as org_id, p.google_place_id, p.legacy_wp_id,
           p.merged_into_id, p.aliases,
           coalesce(m.featured, 0) as featured, coalesce(m.mentions, 0) as mentions,
           coalesce(m.articles, 0) as articles, m.newest
    from public.places p
    left join (
        select pm.place_id,
               count(*) filter (where pm.role = 'featured') as featured,
               count(*) as mentions,
               count(distinct pm.article_id) as articles,
               max(a.published_at) as newest
        from public.place_mentions pm
        left join public.articles a on a.id = pm.article_id
        group by pm.place_id
    ) m on m.place_id = p.id
    order by p.id
    """
)


def fetch_evidence(engine: Engine) -> list[PlaceEvidence]:
    with engine.connect() as conn:
        rows = conn.execute(_EVIDENCE_SQL).mappings().all()
    return [PlaceEvidence(**dict(r)) for r in rows]


def total_featured_mentions(engine: Engine) -> int:
    with engine.connect() as conn:
        return int(conn.execute(text("select count(*) from public.place_mentions where role = 'featured'")).scalar() or 0)


def fetch_partnered(site: str, *, platform_db: str = "now_platform") -> tuple[set[str], set[str]] | None:
    """(place ids as text, org ids as text) with an ACTIVE partnership on
    this site. `engine.partnerships` is RLS-scoped by `app.site_id`
    (migration 0017), so the site is set for the transaction even though
    today's superuser connection bypasses the policy. Returns None if the
    platform database cannot be read -- ranking then scores the
    partnership term as 0 and the report says so."""
    try:
        eng = create_engine(city_database_url(platform_db))
        with eng.begin() as conn:
            site_id = conn.execute(text("select id from engine.sites where slug = :s"), {"s": site}).scalar()
            if site_id is None:
                return set(), set()
            conn.execute(text("select set_config('app.site_id', :sid, true)"), {"sid": str(site_id)})
            rows = conn.execute(
                text(
                    "select place_id, org_id::text from engine.partnerships "
                    "where site_id = :sid and status = 'active' "
                    "and (ends_at is null or ends_at > now())"
                ),
                {"sid": site_id},
            ).all()
        eng.dispose()
    except Exception:  # noqa: BLE001 -- any failure degrades to "no partnership term"
        return None
    places = {r[0] for r in rows if r[0]}
    orgs = {r[1] for r in rows if r[1]}
    return places, orgs


# ------------------------------------------------------------- triage writes

def apply_junk(conn: Connection, ids: list[int]) -> list[int]:
    """Sets `status = 'junk'` on the given rows -- only those still
    `pending_review` and not merged. An `active` or `closed` row is an
    editor's decision and is never overwritten by a heuristic. Returns the
    ids actually changed."""
    if not ids:
        return []
    rows = conn.execute(
        text(
            "update public.places set status = 'junk', updated_at = now() "
            "where id = any(:ids) and status = 'pending_review' and merged_into_id is null "
            "returning id"
        ),
        {"ids": ids},
    ).all()
    return sorted(r[0] for r in rows)


def revert_junk(conn: Connection, ids: list[int]) -> list[int]:
    if not ids:
        return []
    rows = conn.execute(
        text(
            "update public.places set status = 'pending_review', updated_at = now() "
            "where id = any(:ids) and status = 'junk' returning id"
        ),
        {"ids": ids},
    ).all()
    return sorted(r[0] for r in rows)


def write_quality_scores(conn: Connection, scores: dict[int, float]) -> int:
    if not scores:
        return 0
    ids = list(scores)
    vals = [round(scores[i], 3) for i in ids]
    res = conn.execute(
        text(
            "update public.places p set quality_score = s.score "
            "from unnest(cast(:ids as int[]), cast(:vals as numeric[])) as s(id, score) "
            "where p.id = s.id and p.quality_score is distinct from s.score"
        ),
        {"ids": ids, "vals": vals},
    )
    return res.rowcount or 0
