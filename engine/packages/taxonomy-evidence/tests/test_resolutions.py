"""Hansel's answers are applied completely and exactly -- no DB, corpus or network.

The one integration-flavoured test (`test_delta_against_the_generated_pack`)
reads the committed review JSON and the seed files from the repo; it skips when
they are absent so the unit run never depends on them.
"""
import json
from pathlib import Path

import pytest

from now_taxonomy_evidence.decide import CityBuild, PER_ARTICLE_ORDER
from now_taxonomy_evidence.proposals import BALI_PROPOSALS, DECISIONS, JAKARTA_ADJUSTMENTS
from now_taxonomy_evidence.render import render_json, render_markdown
from now_taxonomy_evidence.resolutions import CATEGORY_RESOLUTIONS, EVIDENCE_FLAG_POLICY, RESOLUTIONS, RULES
from now_taxonomy_evidence.vocabulary_delta import CANDIDATE_ACTIONS, DROPS, MATCH_HINTS, PAYLOAD_ENUMS, THRESHOLD, TRIMS, DeltaError, build_delta

# Hansel's eight answer rows, as decision ids (two rows cover several ids).
EXPLICIT_IDS = {"D01", "D02", "D06", "D08", "D09", "D10", "D14", "D15", "D16", "D21", "D22", "D26"}


def test_every_decision_has_exactly_one_resolution():
    ids = {d["id"] for d in DECISIONS}
    assert set(RESOLUTIONS) == ids, "every registry decision must be resolved, and nothing else"
    for did, r in RESOLUTIONS.items():
        assert r["source"] in ("explicit", "as-recommended"), did
        assert r["answer"] and r["option"] and r["rationale"], did
        assert isinstance(r["conflicts"], list) and isinstance(r["applies"], list), did


def test_the_explicit_answers_are_hansels_eight_rows():
    explicit = {did for did, r in RESOLUTIONS.items() if r["source"] == "explicit"}
    assert explicit == EXPLICIT_IDS
    # conflicts are reported on the decisions where the answer diverges from the recommendation
    assert RESOLUTIONS["D08"]["conflicts"] and RESOLUTIONS["D09"]["conflicts"] and RESOLUTIONS["D06"]["conflicts"] and RESOLUTIONS["D14"]["conflicts"]
    assert RESOLUTIONS["D24"]["conflicts"], "the Stranger In Paradise text/table inconsistency must be reported"


def test_category_resolutions_reference_known_categories_and_decisions():
    known = {"bali": set(BALI_PROPOSALS), "jakarta": set(JAKARTA_ADJUSTMENTS)}
    for city, table in CATEGORY_RESOLUTIONS.items():
        for name, ov in table.items():
            assert name in known[city], f"{city}/{name} is not a known category"
            for b in ov.get("basis", []):
                assert b == EVIDENCE_FLAG_POLICY["id"] or b in RESOLUTIONS, f"{city}/{name}: {b}"
            for d in ov.get("decisions_add", []):
                assert d in RESOLUTIONS
            assert set(ov.get("per_article", [])) <= set(PER_ARTICLE_ORDER), f"{city}/{name}"
            if "facets" in ov:
                assert all(isinstance(v, list) for v in ov["facets"].values())


def test_evidence_flag_policy_covers_every_flag_resolution():
    covered = {(a["city"], a["category"]) for a in EVIDENCE_FLAG_POLICY["applies_to"]}
    by_basis = {(city, name) for city, table in CATEGORY_RESOLUTIONS.items() for name, ov in table.items() if EVIDENCE_FLAG_POLICY["id"] in ov.get("basis", [])}
    assert covered == by_basis


def _record(name, status, proposal, decisions=(), flags=(), kind="editorial", published=10):
    return {
        "name": name, "slug": name.lower(), "term_id": 1, "parent": None, "description": "", "city": "bali", "published": published, "wp_count": published,
        "first_year": 2019, "last_year": 2024, "years": {"2019": published}, "yoast_primary": 0, "cooccurs": [], "single_category_articles": published,
        "proposal": proposal, "kind": kind, "container": False, "confidence": "medium", "reasoning": "r", "alternates": ["x"], "proposal_source": "test", "e14": None,
        "decisions": list(decisions), "auto_proposed": status != "decision-needed", "samples": [], "cues": {"type": {"dist": {}, "coverage": 0, "n_signal": 0}, "format": {"dist": {}, "coverage": 0, "n_signal": 0}},
        "period_stamped_share": 0.0, "roundup_share": 0.0, "fp_density_median": 0.0, "locations": {"top": [], "outside_home_share": 0.0},
        "coherence": None, "llm": None, "flags": list(flags), "status": status,
    }


def _bali_build(records):
    """A CityBuild with only `records` -- plus an unflagged placeholder for every
    other Bali category the override table names, since apply_resolutions()
    (rightly) refuses an override for a category that does not exist."""
    b = CityBuild.__new__(CityBuild)
    b.city = "bali"
    full = dict(records)
    for name in CATEGORY_RESOLUTIONS["bali"]:
        if name not in full:
            full[name] = _record(name, "auto-accepted", {"type": None, "subtype": None, "format": None, "location": "bali", "per_article": ["type", "subtype", "format"], "facets": {}, "series_key": None})
    b.records = full
    return b


def test_apply_resolutions_leaves_no_category_undecided_and_keeps_the_e20_record():
    recs = {
        "News": _record("News", "decision-needed", {"type": None, "subtype": None, "format": "news", "location": "bali", "per_article": ["type", "subtype"], "facets": {}, "series_key": None}, ["D21"], published=1067),
        "Chaine Des Rottiseurs": _record("Chaine Des Rottiseurs", "decision-needed", {"type": "eat", "subtype": "fine-dining", "format": "event", "location": "bali", "per_article": [], "facets": {}, "series_key": "column:x"}, ["D08", "D02"], flags=["cue instrument disagrees on format"]),
        "Weddings": _record("Weddings", "decision-needed", {"type": None, "subtype": None, "format": "listing", "location": "bali", "per_article": ["type", "subtype", "format"], "facets": {"occasion": ["celebration"]}, "series_key": None}, ["D22", "D01"]),
        "Must Watch Movies": _record("Must Watch Movies", "decision-needed", {"type": "editorial", "subtype": "lifestyle", "format": "feature", "location": None, "per_article": [], "facets": {}, "series_key": "column:m"}, ["D08", "D05"]),
        "Reviews": _record("Reviews", "auto-accepted", {"type": "eat", "subtype": "restaurant", "format": "review", "location": "bali", "per_article": [], "facets": {}, "series_key": None}),
        "Archives": _record("Archives", "empty", {"type": None, "subtype": None, "format": None, "location": "bali", "per_article": ["type", "subtype", "format"], "facets": {}, "series_key": None}, ["D27"], published=0),
    }
    b = _bali_build(recs)
    b.apply_resolutions()
    assert not [r for r in recs.values() if r["status"] in ("decision-needed", "flagged-by-evidence")]
    assert recs["Archives"]["status"] == "empty"
    ch = recs["Chaine Des Rottiseurs"]
    assert ch["proposal"]["format"] == "review" and "format" in ch["proposal"]["per_article"]
    assert ch["e20_proposal"]["format"] == "event" and ch["e20_status"] == "decision-needed"
    assert ch["resolution"]["changed"] and ch["resolution"]["changes"]["format"] == {"from": "event", "to": "review"}
    assert ch["resolution"]["addressed_flags"] == ["cue instrument disagrees on format"]
    assert ch["status"].startswith("resolved — changed")
    assert recs["Weddings"]["proposal"]["facets"]["occasion"] == ["wedding"]
    assert recs["Must Watch Movies"]["proposal"]["location"] == "bali"
    assert recs["News"]["resolution"]["changed"] is False and recs["News"]["status"] == "resolved (D21)"
    assert recs["Reviews"]["status"] == "resolved (as proposed)"


def test_apply_resolutions_fails_loudly_on_an_unaddressed_flag():
    recs = {"Reviews": _record("Reviews", "flagged-by-evidence", {"type": "eat", "subtype": "restaurant", "format": "review", "location": "bali", "per_article": [], "facets": {}, "series_key": None}, flags=["clusters split the category"])}
    b = _bali_build(recs)
    with pytest.raises(RuntimeError):
        b.apply_resolutions()


def test_rules_block_encodes_the_international_answer():
    intl = RULES["location"]["international"]
    assert "row2_nearby" in intl["excluded"] and "itinerary builder" in intl["excluded"]
    assert any("row3" in e for e in intl["eligible"]) and "search" in intl["eligible"]
    assert intl["attribute"] == {"key": "geo_scope", "value": "abroad", "inherited_by_descendants": True, "default_elsewhere": "home"}
    for k in ("where", "enforced_by", "why_not_a_facet_flag", "why_not_rails_only_code", "prerequisite"):
        assert intl["encoding"][k]
    assert RULES["prior_resolution"]["order"] == ["yoast_primary", "deepest_child", "parent_container"]
    assert RULES["legacy_expiry"]["offer"]["ends_at"].endswith("90 days") and RULES["legacy_expiry"]["event"]["ends_at"].endswith("30 days")
    assert RULES["guide_vs_listing"]["listing"]["half_life_days"] == 540
    assert RULES["migration_scope"]["excluded_categories"] == []
    assert RULES["confidence_gate"]["auto_apply_at_or_above"] == 0.85


def test_delta_tables_are_well_formed():
    assert {(d["facet"], d["slug"]) for d in DROPS} == {("location", "rawamangun")}
    trimmed = {(t["facet"], t["slug"], a) for t in TRIMS for a in t["remove"]}
    for must in {("cuisine", "javanese", "Solo"), ("occasion", "celebration", "party"), ("audience", "business-traveller", "business"), ("location", "malang", "Batu"), ("location", "gunawarman", "Wijaya")}:
        assert must in trimmed, must
    seen = set()
    for key, act in CANDIDATE_ACTIONS.items():
        assert act["action"] in ("add_term", "add_alias", "merge", "skip"), key
        if act["action"] == "add_term":
            assert act["facet"] in (*PAYLOAD_ENUMS, "occasion", "audience", "topic"), key
            assert act["slug"] == act["slug"].lower() and " " not in act["slug"], key
            assert (act["facet"], act["slug"]) not in seen, f"duplicate {key}"
            seen.add((act["facet"], act["slug"]))
            if act["facet"] == "subtype":
                assert act["parent"] in ("stay", "eat", "drink", "do", "wellness", "shop", "event", "editorial"), key
            if act["facet"] == "location":
                assert act["parent"] and act["geo"], key
        if act["action"] == "merge":
            tgt = CANDIDATE_ACTIONS[act["into"]]
            assert tgt["action"] in ("add_term", "add_alias"), key
    assert {h["slug"] for h in MATCH_HINTS} >= {"solo", "kuningan", "party", "international"}


def _repo_root() -> Path | None:
    for p in Path(__file__).resolve().parents:
        if (p / "ARCHITECTURE.md").is_file():
            return p
    return None


def test_delta_against_the_generated_pack():
    root = _repo_root()
    pack = root / "jakarta" / "site" / "taxonomy-review.json" if root else None
    if not root or not pack.is_file():
        pytest.skip("generated pack not present")
    from now_taxonomy_evidence.sources import load_seed
    vocab = json.load(open(pack, encoding="utf-8"))["vocabulary"]
    vocab["_all_candidates"] = vocab["candidates"]
    delta = build_delta(vocab, load_seed(root))
    c = delta["counts"]
    assert c["drop_term"] == 1 and delta["drop_term"][0]["slug"] == "rawamangun"
    assert all(t["mentions"]["total"] >= THRESHOLD for t in delta["add_term"])
    assert all(b["mentions"]["total"] < THRESHOLD for b in delta["below_threshold"])
    assert c["add_term"] + c["add_alias_sets"] > 0 and c["approve"] > 0
    intl = [t for t in delta["add_term"] if t["parent"] == "international"]
    assert intl and all(t["attrs"]["geo_scope"] == "abroad" for t in intl)
    assert all(t["requires_migration"] == (t["facet"] in PAYLOAD_ENUMS) for t in delta["add_term"])
    # every >= threshold candidate is accounted for exactly once
    accounted = {t["from_candidate"] for t in delta["add_term"]} | {k for a in delta["add_alias"] for k in a["from_candidates"] if "(alias suggestion)" not in k} | {m["candidate"] for m in delta["merged"]} | {s["candidate"] for s in delta["skipped"]}
    assert accounted == {r["key"] for r in vocab["candidates"] if r["total"] >= THRESHOLD}
    # a stale curated key must be caught
    vocab2 = dict(vocab)
    vocab2["candidates"] = [r for r in vocab["candidates"] if r["key"] != "vibe/Chic"]
    vocab2["_all_candidates"] = vocab2["candidates"]
    with pytest.raises(DeltaError):
        build_delta(vocab2, load_seed(root))


def test_resolved_model_renders_from_one_dict():
    cat = _record("Chaine Des Rottiseurs", "decision-needed", {"type": "eat", "subtype": "fine-dining", "format": "event", "location": "bali", "per_article": [], "facets": {}, "series_key": "column:x"}, ["D08", "D02"], flags=["f"])
    b = _bali_build({"Chaine Des Rottiseurs": cat})
    b.apply_resolutions()
    d = {**next(d for d in DECISIONS if d["id"] == "D08"), "affects": [], "articles_affected": 24, "evidence": [], "cities": ["bali"], "status": "resolved", "resolution": {**RESOLUTIONS["D08"], "status": "resolved"}}
    model = {
        "city": "bali", "generated": "now", "tool": "t", "llm": {"path": "heuristic-only"}, "sources": {}, "vector_source": "tfidf-proxy",
        "resolution_meta": {"decided_by": "Hansel", "decided_on": "2026-09-10", "decisions_total": 27, "decisions_resolved": 27, "decisions_open": [], "explicit": sorted(EXPLICIT_IDS), "as_recommended": [], "conflicts_with_recommendation": []},
        "decisions": [d], "evidence_flag_policy": EVIDENCE_FLAG_POLICY, "rules": RULES, "vocabulary_delta": {"file": "f", "human": "h", "counts": None},
        "cross_city": [], "instrument_calibration": [],
        "vocabulary": {"method": "m", "articles_scanned": {"bali": 1}, "total_articles": 1, "seed_terms": [], "seed_unused": [], "seed_rare": [], "candidates": [], "candidate_threshold": 12, "tags_uncovered": {}},
        "totals": {"articles": 24, "categories": 1, "categories_with_articles": 1, "flagged_categories": 0, "decision_needed_categories": 0, "resolved_categories": 1, "changed_categories": 1,
                   "flagged_categories_pre_resolution": 1, "auto_accepted_categories": 0, "empty_categories": 0, "status_counts": {}, "decisions_total": 27, "decisions_for_city": 1, "decisions_resolved": 1},
        "categories": [cat], "coherence_summary": {},
    }
    md = render_markdown(model)
    js = json.loads(render_json(model))
    assert "RESOLVED" in md and "## 1. Decisions — all resolved" in md and "## 7. Classification rules" in md
    assert "Resolved (explicit" in md and "Conflicts with the E2.0 recommendation" in md
    assert js["categories"][0]["proposal"]["format"] == "review" and js["categories"][0]["e20_proposal"]["format"] == "event"
    assert js["decisions"][0]["resolution"]["source"] == "explicit"
    assert "row2_nearby" in md and "geo_scope" in md
