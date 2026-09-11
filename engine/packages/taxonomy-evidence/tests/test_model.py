"""Model-level invariants that need no DB, corpus or network."""
import json

import numpy as np

from now_taxonomy_evidence import coherence as coh
from now_taxonomy_evidence.decide import _spread
from now_taxonomy_evidence.proposals import BALI_PROPOSALS, DECISIONS, JAKARTA_ADJUSTMENTS
from now_taxonomy_evidence.render import render_json, render_markdown
from now_taxonomy_evidence.sources import Article
from now_taxonomy_evidence.text import FORMATS, TYPES
from now_taxonomy_evidence.vectors import VectorSpace
from now_taxonomy_evidence.vocabulary import _Matcher


def test_spread_samples_across_the_range_not_the_head():
    items = list(range(100))
    picked = _spread(items, 8)
    assert picked[0] == 0 and picked[-1] == 99 and len(picked) == 8
    assert picked == sorted(picked)
    assert _spread([1, 2, 3], 8) == [1, 2, 3]


def test_decision_registry_is_well_formed_and_referenced():
    ids = [d["id"] for d in DECISIONS]
    assert len(ids) == len(set(ids))
    assert 20 <= len(ids) <= 35, "the flagged set should be ~20-35 decisions, not 110"
    for d in DECISIONS:
        assert d["question"] and d["recommendation"] and d["options"]
        assert d["kind"] in ("policy", "vocabulary", "mapping", "split", "scope")
    referenced = {x for p in BALI_PROPOSALS.values() for x in p["decisions"]} | {x for a in JAKARTA_ADJUSTMENTS.values() for x in a.get("decisions", [])} | {"D07"}
    assert referenced <= set(ids)
    # every decision is reachable from at least one category or is cross-cutting vocabulary/policy
    for d in DECISIONS:
        assert d["id"] in referenced or d["kind"] in ("vocabulary", "policy"), d["id"]


def test_bali_proposals_use_only_vocabulary_values():
    for name, p in BALI_PROPOSALS.items():
        assert p["type"] in (None, *TYPES), name
        assert p["format"] in (None, *FORMATS), name
        assert set(p["per_article"]) <= {"type", "subtype", "format", "location"}, name
        assert p["reasoning"], name


def test_matcher_counts_every_owner_of_a_surface_form():
    m = _Matcher({"subtype/spa": ["Spa", "massage"], "amenities/spa": ["Spa", "in-house spa"], "cuisine/italian": ["Italian", "pizza"]})
    keys = m.keys_in("A day at the spa, then pizza.")
    assert keys == {"subtype/spa", "amenities/spa", "cuisine/italian"}
    assert m.keys_in("nothing here") == set()


def _space(n=40, d=8, seed=0):
    rng = np.random.RandomState(seed)
    a = rng.normal(0, 1, (n // 2, d)) + np.array([5] + [0] * (d - 1))
    b = rng.normal(0, 1, (n // 2, d)) + np.array([0, 5] + [0] * (d - 2))
    m = np.vstack([a, b]).astype(np.float32)
    m /= np.linalg.norm(m, axis=1, keepdims=True)
    return VectorSpace("test", "embeddings:test", list(range(1, n + 1)), m, False)


def _articles(n=40):
    return [Article("test", i + 1, f"t{i}", f"s{i}", f"20{10 + i % 15:02d}-01-01", ["Cat"], None, "", "", None, None) for i in range(n)]


def test_coherence_detects_a_venue_type_split():
    space = _space()
    arts = _articles()
    feats = {a.wp_id: {"type": "eat" if a.wp_id <= 20 else "stay", "format": "offer"} for a in arts}
    curve = coh.baseline_curve(space, sizes=(8, 20, 40), draws=5)
    res = coh.analyse_category("Cat", arts, space, {}, feats, {40: coh.baseline_for(40, curve)}, False, "eat", "offer", __import__("random").Random(0), {})
    assert res.verdict == "incoherent"
    assert res.best_k == 2 and len(res.clusters) == 2
    assert {c.top_type for c in res.clusters} == {"eat", "stay"}
    assert all(len(c.examples) >= 1 for c in res.clusters)


def test_coherence_expected_heterogeneous_is_not_flagged():
    space = _space()
    arts = _articles()
    feats = {a.wp_id: {"type": "eat" if a.wp_id <= 20 else "stay", "format": None} for a in arts}
    curve = coh.baseline_curve(space, sizes=(8, 20, 40), draws=5)
    res = coh.analyse_category("Cat", arts, space, {}, feats, {40: coh.baseline_for(40, curve)}, True, None, None, __import__("random").Random(0), {})
    assert res.verdict == "expected-heterogeneous"


def _minimal_model():
    cat = {
        "name": "Dining News", "slug": "dining-news", "term_id": 1, "parent": "Dining", "description": "", "city": "jakarta", "published": 3, "wp_count": 3,
        "first_year": 2019, "last_year": 2024, "years": {"2019": 2, "2024": 1}, "yoast_primary": 1, "cooccurs": [], "single_category_articles": 3,
        "proposal": {"type": "eat", "subtype": "restaurant", "format": "news", "location": "jakarta", "per_article": [], "facets": {}, "series_key": None},
        "kind": "editorial", "container": False, "confidence": "high", "reasoning": "r", "alternates": [], "proposal_source": "E1.4", "e14": None,
        "decisions": [], "auto_proposed": True, "samples": [{"wp_id": 1, "date": "2019-01-01", "title": "A | B"}],
        "cues": {"type": {"dist": {"eat": 1.0}, "coverage": 1.0, "n_signal": 3}, "format": {"dist": {}, "coverage": 0.0, "n_signal": 0}},
        "period_stamped_share": 0.0, "roundup_share": 0.0, "fp_density_median": 1.0, "locations": {"top": [], "outside_home_share": 0.0},
        "coherence": None, "llm": None, "flags": [], "status": "auto-accepted",
    }
    return {
        "city": "jakarta", "generated": "now", "tool": "t", "llm": {"path": "heuristic-only"}, "sources": {}, "vector_source": "embeddings:x",
        "decisions": [{"id": "D01", "kind": "policy", "title": "T", "question": "Q", "recommendation": "R", "options": ["a"], "carried_from": None,
                       "affects": [{"city": "jakarta", "category": "Dining News", "articles": 3}], "articles_affected": 3, "evidence": ["e"], "cities": ["jakarta"]}],
        "cross_city": [], "instrument_calibration": [],
        "vocabulary": {"method": "m", "articles_scanned": {"jakarta": 3}, "total_articles": 3, "seed_terms": [], "seed_unused": [], "seed_rare": [], "candidates": [], "candidate_threshold": 12, "tags_uncovered": {}},
        "totals": {"articles": 3, "categories": 1, "categories_with_articles": 1, "flagged_categories": 0, "auto_accepted_categories": 1, "empty_categories": 0,
                   "status_counts": {"auto-accepted": 1}, "decisions_total": 1, "decisions_for_city": 1},
        "categories": [cat], "coherence_summary": {},
    }


def test_markdown_and_json_render_from_the_same_model():
    model = _minimal_model()
    md = render_markdown(model)
    js = json.loads(render_json(model))
    assert "## 1. Decisions needed" in md and "D01" in md
    assert "Dining News" in md and "A \\| B" in md  # pipes escaped in tables
    assert js["categories"][0]["name"] == "Dining News"
    assert js["decisions"][0]["id"] == "D01"
    assert md.index("## 1. Decisions needed") < md.index("## Appendix A")
