"""Resolves facet slugs (type/subtype/format/location) to platform term
uuids, read-only, once per run (F92: no FK, no cross-DB join possible --
`now_platform.engine.terms` must be resolved application-side and cached).
"""
from __future__ import annotations

from dataclasses import dataclass

from now_platform_db.settings import platform_database_url
from sqlalchemy import create_engine, text


@dataclass
class TermIndex:
    # facet_key -> {slug: (uuid_str, parent_slug | None)}
    by_facet: dict[str, dict[str, tuple[str, str | None]]]
    international_children: set[str]  # location slugs under geo_scope=abroad (incl. "international" itself)


def load_term_index() -> TermIndex:
    eng = create_engine(platform_database_url())
    by_facet: dict[str, dict[str, tuple[str, str | None]]] = {}
    with eng.connect() as conn:
        rows = conn.execute(
            text(
                """
                select f.key as facet_key, t.slug, t.id::text as term_id, p.slug as parent_slug
                from engine.terms t
                join engine.facets f on f.id = t.facet_id
                left join engine.terms p on p.id = t.parent_id
                """
            )
        ).mappings().all()
        for r in rows:
            by_facet.setdefault(r["facet_key"], {})[r["slug"]] = (r["term_id"], r["parent_slug"])

        # geo_scope=abroad: "international" plus every descendant (F88's attrs fix).
        abroad_rows = conn.execute(
            text(
                """
                with recursive tree as (
                    select t.id, t.slug from engine.terms t
                    join engine.facets f on f.id = t.facet_id
                    where f.key = 'location' and t.slug = 'international'
                    union all
                    select c.id, c.slug from engine.terms c
                    join tree on c.parent_id = tree.id
                )
                select slug from tree
                """
            )
        ).fetchall()
        international_children = {r[0] for r in abroad_rows}
    return TermIndex(by_facet=by_facet, international_children=international_children)


def term_uuid(index: TermIndex, facet_key: str, slug: str | None) -> str | None:
    if not slug:
        return None
    entry = index.by_facet.get(facet_key, {}).get(slug)
    return entry[0] if entry else None
