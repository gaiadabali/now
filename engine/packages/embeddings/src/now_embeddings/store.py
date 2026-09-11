"""All SQL for the embeddings pipeline: read the embeddable entities (raw
SQL against Payload-owned `public` tables and the platform's
`engine.terms`), read+write `engine.embeddings` itself, and the HNSW kNN
query. Deliberately raw SQL (`sqlalchemy.text`), matching this monorepo's
convention (now_loader, now_geocode) of not putting an ORM in front of
tables this package does not own the migrations for.

Vector literal note: pgvector's Python drivers (`pgvector-python`) are not
a dependency here -- a `vector` column accepts a plain text literal like
`'[0.1,0.2,...]'` cast with `::vector`, which is all `_vec_literal` builds.
The values going into that string are always floats produced by our own
provider (never user input), so building it with an f-string is not an
injection risk -- the same reasoning `now_loader` and `now_geocode` already
apply to their own generated SQL fragments.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.engine import Connection

from now_embeddings.textbuild import build_article_text, build_place_text, build_term_text


@dataclass(frozen=True)
class EmbeddableRow:
    entity_type: str
    entity_id: str
    text: str
    text_hash: str


def _vec_literal(vec: list[float]) -> str:
    return "[" + ",".join(f"{v:.8f}" for v in vec) + "]"


# --------------------------------------------------------------------------
# Fetch: entity source tables (Payload `public` in the city DB, or the
# platform's shared `engine.terms`) -- read-only, never written by this
# package.
# --------------------------------------------------------------------------


def fetch_articles(conn: Connection) -> list[EmbeddableRow]:
    rows = conn.execute(
        text(
            """
            SELECT id, title, dek, body_blocks, primary_type::text, format::text
              FROM public.articles
             WHERE _status = 'published'
             ORDER BY id
            """
        )
    ).fetchall()
    out = []
    for r in rows:
        article_id, title, dek, body_blocks, primary_type, fmt = r
        txt, digest = build_article_text(
            title=title,
            dek=dek,
            body_blocks=body_blocks or [],
            primary_type=primary_type,
            format=fmt,
        )
        out.append(EmbeddableRow("article", str(article_id), txt, digest))
    return out


def fetch_places(conn: Connection) -> list[EmbeddableRow]:
    rows = conn.execute(
        text(
            """
            SELECT p.id, p.name, p.address, p.area_term::text, p.type::text,
                   p.subtype::text, p.price_band::text,
                   COALESCE(array_agg(DISTINCT a.value::text) FILTER (WHERE a.value IS NOT NULL), '{}'),
                   COALESCE(array_agg(DISTINCT c.value::text) FILTER (WHERE c.value IS NOT NULL), '{}'),
                   COALESCE(array_agg(DISTINCT v.value::text) FILTER (WHERE v.value IS NOT NULL), '{}')
              FROM public.places p
              LEFT JOIN public.places_amenities a ON a.parent_id = p.id
              LEFT JOIN public.places_cuisine c ON c.parent_id = p.id
              LEFT JOIN public.places_vibe v ON v.parent_id = p.id
             GROUP BY p.id
             ORDER BY p.id
            """
        )
    ).fetchall()
    out = []
    for r in rows:
        place_id, name, address, area_term, ptype, subtype, price_band, amenities, cuisine, vibe = r
        txt, digest = build_place_text(
            name=name,
            address=address,
            area_term=area_term,
            place_type=ptype,
            subtype=subtype,
            price_band=price_band,
            amenities=list(amenities or []),
            cuisine=list(cuisine or []),
            vibe=list(vibe or []),
        )
        out.append(EmbeddableRow("place", str(place_id), txt, digest))
    return out


def fetch_terms(platform_conn: Connection) -> list[EmbeddableRow]:
    """Reads `now_platform.engine.terms` -- a different database from the
    city DB the rest of this module operates on. Term embeddings are still
    *written* into the city's `engine.embeddings` (see README "Where term
    embeddings live and why"), so the caller passes a connection to
    `now_platform` here and a connection to the city DB to `upsert_batch`.
    """
    rows = platform_conn.execute(
        text(
            """
            SELECT t.id, t.slug, t.label, f.key
              FROM engine.terms t
              JOIN engine.facets f ON f.id = t.facet_id
             ORDER BY t.id
            """
        )
    ).fetchall()
    out = []
    for term_id, slug, label, facet_key in rows:
        txt, digest = build_term_text(facet_key=facet_key, label=label, slug=slug)
        out.append(EmbeddableRow("term", str(term_id), txt, digest))
    return out


FETCHERS = {
    "article": fetch_articles,
    "place": fetch_places,
}


def fetch_article_by_id(conn: Connection, article_id: str) -> EmbeddableRow | None:
    """Single-row counterpart to `fetch_articles`, used by the publish-event
    worker so a re-embed on publish is one indexed lookup, not a full-table
    scan of all 4,772 articles per event."""
    row = conn.execute(
        text(
            """
            SELECT id, title, dek, body_blocks, primary_type::text, format::text
              FROM public.articles
             WHERE id = :id AND _status = 'published'
            """
        ),
        {"id": article_id},
    ).first()
    if row is None:
        return None
    article_id_, title, dek, body_blocks, primary_type, fmt = row
    txt, digest = build_article_text(
        title=title, dek=dek, body_blocks=body_blocks or [], primary_type=primary_type, format=fmt
    )
    return EmbeddableRow("article", str(article_id_), txt, digest)


def fetch_place_by_id(conn: Connection, place_id: str) -> EmbeddableRow | None:
    row = conn.execute(
        text(
            """
            SELECT p.id, p.name, p.address, p.area_term::text, p.type::text,
                   p.subtype::text, p.price_band::text,
                   COALESCE(array_agg(DISTINCT a.value::text) FILTER (WHERE a.value IS NOT NULL), '{}'),
                   COALESCE(array_agg(DISTINCT c.value::text) FILTER (WHERE c.value IS NOT NULL), '{}'),
                   COALESCE(array_agg(DISTINCT v.value::text) FILTER (WHERE v.value IS NOT NULL), '{}')
              FROM public.places p
              LEFT JOIN public.places_amenities a ON a.parent_id = p.id
              LEFT JOIN public.places_cuisine c ON c.parent_id = p.id
              LEFT JOIN public.places_vibe v ON v.parent_id = p.id
             WHERE p.id = :id
             GROUP BY p.id
            """
        ),
        {"id": place_id},
    ).first()
    if row is None:
        return None
    place_id_, name, address, area_term, ptype, subtype, price_band, amenities, cuisine, vibe = row
    txt, digest = build_place_text(
        name=name,
        address=address,
        area_term=area_term,
        place_type=ptype,
        subtype=subtype,
        price_band=price_band,
        amenities=list(amenities or []),
        cuisine=list(cuisine or []),
        vibe=list(vibe or []),
    )
    return EmbeddableRow("place", str(place_id_), txt, digest)


# --------------------------------------------------------------------------
# engine.embeddings: read (for the idempotency check) + write
# --------------------------------------------------------------------------


def existing_hashes(conn: Connection, entity_type: str, model: str) -> dict[str, str]:
    """entity_id -> text_hash for every row already embedded under this
    (entity_type, model). The pipeline diffs against this before calling
    the provider at all -- an unchanged hash means an unchanged input text,
    which means an unchanged embedding, so skipping it is not an
    approximation, it is the exact same output the model would produce."""
    rows = conn.execute(
        text("SELECT entity_id, text_hash FROM engine.embeddings WHERE entity_type = :et AND model = :model"),
        {"et": entity_type, "model": model},
    ).fetchall()
    return {r[0]: r[1] for r in rows}


def upsert_batch(
    conn: Connection,
    *,
    entity_type: str,
    model: str,
    dim: int,
    rows: list[tuple[str, list[float], str]],  # (entity_id, vec, text_hash)
) -> None:
    for entity_id, vec, text_hash in rows:
        conn.execute(
            text(
                """
                INSERT INTO engine.embeddings (entity_type, entity_id, model, dim, vec, text_hash, updated_at)
                VALUES (:et, :eid, :model, :dim, CAST(:vec AS vector), :hash, now())
                ON CONFLICT (entity_type, entity_id, model) DO UPDATE SET
                    dim = EXCLUDED.dim,
                    vec = EXCLUDED.vec,
                    text_hash = EXCLUDED.text_hash,
                    updated_at = now()
                """
            ),
            {
                "et": entity_type,
                "eid": entity_id,
                "model": model,
                "dim": dim,
                "vec": _vec_literal(vec),
                "hash": text_hash,
            },
        )


def delete_stale(conn: Connection, *, entity_type: str, model: str, keep_entity_ids: set[str]) -> int:
    """Removes embeddings for entities that no longer exist in the source
    table (e.g. a place deleted in Payload) -- keeps `engine.embeddings`
    from accumulating rows for entities the rest of the engine can never
    look up again. Not called for `term` (the platform vocabulary is not
    expected to shrink during this wave)."""
    if not keep_entity_ids:
        return 0
    result = conn.execute(
        text(
            "DELETE FROM engine.embeddings "
            "WHERE entity_type = :et AND model = :model AND entity_id <> ALL(:keep)"
        ),
        {"et": entity_type, "model": model, "keep": list(keep_entity_ids)},
    )
    return result.rowcount or 0


# --------------------------------------------------------------------------
# kNN
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Neighbor:
    entity_id: str
    cosine_similarity: float


def knn(
    conn: Connection,
    *,
    entity_type: str,
    model: str,
    query_vec: list[float],
    k: int,
    exclude_entity_id: str | None = None,
) -> list[Neighbor]:
    rows = conn.execute(
        text(
            """
            SELECT entity_id, 1 - (vec <=> CAST(:qvec AS vector)) AS cosine_sim
              FROM engine.embeddings
             WHERE entity_type = :et AND model = :model
               AND (CAST(:exclude AS text) IS NULL OR entity_id <> CAST(:exclude AS text))
             ORDER BY vec <=> CAST(:qvec AS vector)
             LIMIT :k
            """
        ),
        {
            "et": entity_type,
            "model": model,
            "qvec": _vec_literal(query_vec),
            "exclude": exclude_entity_id,
            "k": k,
        },
    ).fetchall()
    return [Neighbor(entity_id=r[0], cosine_similarity=float(r[1])) for r in rows]
