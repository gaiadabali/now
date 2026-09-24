"""Embedding signals for WS5 tagging.

Two sources, both reusing `now_taxonomy_evidence.embed_similarity`'s pure
vector math (`cosine`, `build_trusted_centroids`) rather than a second
implementation:

1. **Direct term similarity**: every one of the 407 platform terms is
   ALREADY embedded, in each city DB (`engine.embeddings`, entity_type=
   'term', model BAAI/bge-small-en-v1.5 -- confirmed live: 407 rows in
   both `now_bali` and `now_jakarta`). So `cosine(article_vector,
   term_vector)` needs no training data at all -- it exists the moment an
   article has a vector, which E2.4/E2.4b already backfilled for the
   entire published archive (4,429 Bali / 4,772 Jakarta). This is the
   fallback signal for a term whose label alone is weak lexically (a term
   embedded as "vibe: romantic (romantic)" is still semantically closer to
   a candlelit-dinner review than to a kids'-menu listing, even with zero
   literal alias overlap).

2. **Few-shot centroids**: built from WS5's own hand-labelled calibration
   set (`calibration.py`'s labelled article->term positives) via
   `build_trusted_centroids` -- the SAME function `now_classifier.
   embed_routing` uses for type/format, with the same `min_class_n`
   abstain rule (a term with fewer than 5 labelled positive exemplars gets
   no centroid at all, rather than a centroid that is a mean of almost
   nothing). This is the spec's explicit "few-shot centroids from articles
   whose tags are already known" -- "already known" here means WS5's own
   calibration labels, the only tags that exist for these facets before
   this job runs.

Both scores are plain cosine in [-1, 1]; `combine.py` decides what to do
with them.
"""
from __future__ import annotations

from dataclasses import dataclass

from now_taxonomy_evidence.embed_similarity import Vector, build_trusted_centroids, cosine
from now_taxonomy_evidence.vectors import EMBEDDING_MODEL
from sqlalchemy import text
from sqlalchemy.engine import Engine


def load_term_vectors(engine: Engine, term_ids: list[str], model: str = EMBEDDING_MODEL) -> dict[str, Vector]:
    """term_id (uuid str, lowercased) -> vector, from THIS city's own
    `engine.embeddings` (entity_type='term') -- no cross-DB join, no
    platform-DB round trip; the vectors were already mirrored into each
    city DB by the same embeddings pipeline that embeds articles there."""
    if not term_ids:
        return {}
    rows = engine.connect().execute(
        text(
            "select entity_id, vec::text from engine.embeddings "
            "where entity_type = 'term' and model = :model and entity_id = any(cast(:ids as text[]))"
        ),
        {"model": model, "ids": term_ids},
    ).fetchall()
    return {str(r[0]).lower(): [float(x) for x in r[1].strip("[]").split(",")] for r in rows}


@dataclass(frozen=True)
class CentroidIndex:
    """facet_key -> term_slug -> centroid vector, plus which slugs were
    excluded (too few calibration exemplars) -- disclosed, not hidden, same
    convention as `now_classifier.embed_routing.CentroidModel`."""
    facet: str
    centroids: dict[str, Vector]
    class_n: dict[str, int]
    excluded: frozenset[str]


def build_facet_centroids(facet: str, labelled_positives: list[tuple[str, Vector]], min_class_n: int = 5) -> CentroidIndex:
    """`labelled_positives`: (term_slug, article_vector) pairs from WS5's
    OWN calibration labels for this facet where the human verdict was
    "yes, this term applies" -- never the full unlabelled corpus (that
    would be circular: using the job's own unverified output to build the
    model that decides the job's output)."""
    centroids, class_n, excluded = build_trusted_centroids(labelled_positives, min_class_n=min_class_n)
    return CentroidIndex(facet=facet, centroids=centroids, class_n=class_n, excluded=excluded)


def term_similarity(article_vec: Vector | None, term_vec: Vector | None) -> float:
    if article_vec is None or term_vec is None:
        return 0.0
    return cosine(article_vec, term_vec)


def centroid_similarity(article_vec: Vector | None, slug: str, centroids: CentroidIndex | None) -> float:
    if article_vec is None or centroids is None:
        return 0.0
    c = centroids.centroids.get(slug)
    if c is None:
        return 0.0
    return cosine(article_vec, c)
