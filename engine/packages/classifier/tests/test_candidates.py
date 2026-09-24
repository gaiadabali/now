from __future__ import annotations

from now_classifier.facet_tagging.candidates import (
    BAND_BODY,
    BAND_EMBED_ONLY,
    BAND_TITLE,
    EMBED_ONLY_FLOOR,
    candidates_for_article,
)
from now_classifier.facet_tagging.lexicon import build_term_matcher

SEED = [{"slug": "surf", "label": "Surf", "aliases": ["surfing"]}]
MATCHER = build_term_matcher(SEED)
TERM_VECTORS = {"surf": "11111111-1111-1111-1111-111111111111"}


def test_title_hit_reported_even_with_low_embedding_similarity() -> None:
    cands = candidates_for_article(
        "topic", "A Guide to Surfing", "no lead signal", "filler body text",
        MATCHER, article_vec=[0.0, 1.0], term_vectors=TERM_VECTORS,
        term_vec_by_id={"11111111-1111-1111-1111-111111111111": [1.0, 0.0]},  # orthogonal -> cosine 0
        centroids=None,
    )
    assert len(cands) == 1
    assert cands[0].band == BAND_TITLE
    assert cands[0].slug == "surf"


def test_body_only_lexical_hit_is_reported_as_body_band() -> None:
    # LEAD_CHARS (400) must be safely cleared before the match, or it
    # lands in the lead zone instead of the body zone.
    body = ("filler " * 80) + "a great surfing trip" + (" filler" * 50)
    cands = candidates_for_article(
        "topic", "Nothing Related", "no lead signal either", body,
        MATCHER, article_vec=None, term_vectors=TERM_VECTORS, term_vec_by_id={}, centroids=None,
    )
    assert cands[0].band == BAND_BODY


def test_no_lexical_hit_but_strong_embedding_is_embed_only() -> None:
    vec = [1.0, 0.0]
    cands = candidates_for_article(
        "topic", "Completely Unrelated Title", "no lexical signal", "still nothing lexical",
        MATCHER, article_vec=vec, term_vectors=TERM_VECTORS,
        term_vec_by_id={"11111111-1111-1111-1111-111111111111": vec},  # identical -> cosine 1.0
        centroids=None,
    )
    assert len(cands) == 1
    assert cands[0].band == BAND_EMBED_ONLY
    assert cands[0].direct_sim >= EMBED_ONLY_FLOOR


def test_weak_embedding_below_floor_and_no_lexical_hit_yields_no_candidate() -> None:
    cands = candidates_for_article(
        "topic", "Completely Unrelated Title", "no lexical signal", "still nothing lexical",
        MATCHER, article_vec=[1.0, 0.0], term_vectors=TERM_VECTORS,
        term_vec_by_id={"11111111-1111-1111-1111-111111111111": [0.0, 1.0]},  # orthogonal -> cosine 0
        centroids=None,
    )
    assert cands == []
