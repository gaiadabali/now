"""Drives the two candidate generators E3.1 (`now-search`) exposes --
lexical (`ts_rank_cd`) and semantic (pgvector cosine) -- and shows their
raw, pre-fusion output side by side, then fuses with the same
Reciprocal Rank Fusion `now-search` uses in production.

This module calls `now_search`'s public functions directly
(`lexical.search_lexical`, `semantic.search_semantic`,
`rrf.reciprocal_rank_fusion`, `rrf.to_ranked_hits`) rather than going
through `SearchEngine.search()`, specifically because `SearchEngine`
only returns the *fused* top-k -- the Inspector's job is to show what
each rail produced *before* fusion (ARCHITECTURE.md §17, deliverable 1),
which means calling the same two rail functions `SearchEngine` calls
internally, ourselves. `now_search`'s public signatures are stable and
untouched here (see the ticket brief) -- this only reads them.

Two modes:

* **query mode** -- literal free-text search, exactly what `now-search`
  does for a query string.
* **article-id mode** -- "what would rank near this article". There is
  no "more-like-this" entry point in `now-search`'s public API, so this
  builds the closest honest approximation from primitives already
  public:
    - lexical rail: `title + ' ' + dek` run through the same
      `lexical.search_lexical` the query path uses (documented
      approximation, not a special lexical mode).
    - semantic rail: the article's OWN stored vector
      (`engine.embeddings`, model-filtered per F42) used as the kNN
      query vector, via a SELECT this module owns (same shape as
      `now_search.semantic._KNN_SQL`, since that module doesn't expose
      "kNN from an existing entity_id" as a public function) -- always
      filtered `WHERE model = :model`, matching F42.
"""

from __future__ import annotations

from dataclasses import dataclass

from now_search import lexical as ns_lexical
from now_search import query_embedder as ns_query_embedder
from now_search import semantic as ns_semantic
from now_search.models import FusedHit, RankedHit
from now_search.rrf import DEFAULT_K, reciprocal_rank_fusion, to_ranked_hits
from sqlalchemy import text
from sqlalchemy.engine import Connection

from now_inspector.articles import fetch_articles
from now_inspector.models import GeneratorPanel

_MODEL_NAME = ns_query_embedder.model_name()

_SEED_VECTOR_KNN_SQL = text(
    """
    SELECT e2.entity_id::int AS article_id, 1 - (e2.vec <=> e1.vec) AS cosine_sim
      FROM engine.embeddings e1
      JOIN engine.embeddings e2
        ON e2.entity_type = e1.entity_type AND e2.model = e1.model
     WHERE e1.entity_type = :entity_type
       AND e1.model = :model
       AND e1.entity_id = :seed_entity_id
       AND e2.entity_id <> e1.entity_id
     ORDER BY e2.vec <=> e1.vec
     LIMIT :limit
    """
)


@dataclass(frozen=True)
class RawGenerators:
    lexical_hits: list[RankedHit]
    semantic_hits: list[RankedHit]
    query_used_for_lexical: str
    semantic_seed_note: str


def run_query_mode(conn: Connection, query: str, *, limit: int = 25) -> RawGenerators:
    lexical_hits = ns_lexical.search_lexical(conn, query, limit=limit)

    query_vec = ns_query_embedder.embed_query(query)
    semantic_hits = ns_semantic.search_semantic(conn, query_vec, model=_MODEL_NAME, limit=limit)

    return RawGenerators(
        lexical_hits=lexical_hits,
        semantic_hits=semantic_hits,
        query_used_for_lexical=query,
        semantic_seed_note=f"query text embedded live with {_MODEL_NAME}",
    )


def run_article_id_mode(conn: Connection, article_id: int, *, limit: int = 25) -> RawGenerators:
    seed = fetch_articles(conn, [article_id]).get(article_id)
    seed_text = f"{seed.title} {seed.dek or ''}".strip() if seed else ""
    lexical_hits = ns_lexical.search_lexical(conn, seed_text, limit=limit) if seed_text else []

    row = conn.execute(
        _SEED_VECTOR_KNN_SQL,
        {
            "entity_type": "article",
            "model": _MODEL_NAME,
            "seed_entity_id": str(article_id),
            "limit": limit,
        },
    ).fetchall()
    semantic_hits = to_ranked_hits([(str(r.article_id), float(r.cosine_sim)) for r in row])

    has_embedding = conn.execute(
        text(
            "SELECT 1 FROM engine.embeddings WHERE entity_type = :et AND model = :m AND entity_id = :eid"
        ),
        {"et": "article", "m": _MODEL_NAME, "eid": str(article_id)},
    ).first()

    note = (
        f"kNN against this article's own vector (engine.embeddings, model={_MODEL_NAME!r}, F42 "
        "filter applied)"
        if has_embedding
        else f"NO ROW in engine.embeddings for entity_id={article_id!r}, model={_MODEL_NAME!r} -- "
        "semantic rail returns nothing for this seed; either it postdates the last embeddings "
        "run, or the model filter is correctly excluding a stale row under a different model."
    )

    return RawGenerators(
        lexical_hits=lexical_hits,
        semantic_hits=semantic_hits,
        query_used_for_lexical=seed_text or "(no title/dek on seed article -- lexical rail empty)",
        semantic_seed_note=note,
    )


def fuse(raw: RawGenerators, *, rrf_k: float = DEFAULT_K) -> list[FusedHit]:
    return reciprocal_rank_fusion(raw.lexical_hits, raw.semantic_hits, k=rrf_k)


def to_panels(raw: RawGenerators, titles: dict[int, str]) -> list[GeneratorPanel]:
    def hit_dict(h: RankedHit) -> dict:
        eid = int(h.entity_id)
        return {"rank": h.rank, "entity_id": h.entity_id, "raw_score": h.raw_score, "title": titles.get(eid, "?")}

    return [
        GeneratorPanel(
            name="Lexical (ts_rank_cd)",
            description=f"Postgres full-text over the materialised engine.article_search.tsv "
            f"(now_search.lexical). Query used: {raw.query_used_for_lexical!r}.",
            hits=[hit_dict(h) for h in raw.lexical_hits],
            candidate_count=len(raw.lexical_hits),
        ),
        GeneratorPanel(
            name="Semantic (cosine, pgvector)",
            description=f"kNN over engine.embeddings, {raw.semantic_seed_note}.",
            hits=[hit_dict(h) for h in raw.semantic_hits],
            candidate_count=len(raw.semantic_hits),
        ),
    ]
