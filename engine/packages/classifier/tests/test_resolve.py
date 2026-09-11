import pytest
from now_taxonomy_evidence.sources import Article

from now_classifier.review_doc import CategoryResolution, D10Result
from now_classifier.resolve import _mixed_categories_override, classify_article
from now_classifier.vocabulary import TermIndex


def _article(**kw):
    base = dict(city="jakarta", wp_id=1, title="t", slug="t", date="2019-01-01",
                categories=[], primary_category_id=None, excerpt="", text="", focus_kw=None, views=None)
    base.update(kw)
    return Article(**base)


def _terms():
    return TermIndex(
        by_facet={
            "type": {"eat": ("uuid-eat", None), "drink": ("uuid-drink", None), "stay": ("uuid-stay", None)},
            "subtype": {"restaurant": ("uuid-restaurant", "eat"), "bar": ("uuid-bar", "drink")},
            "format": {"review": ("uuid-review", None), "offer": ("uuid-offer", None), "news": ("uuid-news", None)},
            "location": {"jakarta": ("uuid-jakarta", "indonesia"), "bali": ("uuid-bali", "indonesia"),
                         "bandung": ("uuid-bandung", "other")},
        },
        international_children=set(),
    )


def _fixed_res(**proposal_overrides):
    proposal = {"type": "eat", "subtype": "restaurant", "format": "review", "location": "jakarta", "per_article": []}
    proposal.update(proposal_overrides)
    return CategoryResolution(term_id=1, name="Reviews", slug="reviews", container=False,
                               confidence="high", reasoning="test category", proposal=proposal, decisions=[])


def test_fixed_category_facets_all_clear_the_gate():
    a = _article(title="Some Review", text="A nice restaurant review.")
    res = _fixed_res()
    d10 = D10Result(res, "yoast_primary")
    r = classify_article(a, d10, {"type": None, "format": None, "type_scores": {}, "format_scores": {}}, _terms())
    # F120 routing: category_fixed_high (conf_label="high") routes to
    # keyword_cue/category prior -- same VALUE as before, but the
    # confidence is now the MEASURED, FACET-SCOPED accuracy (0.760 for
    # type, 0.560 for format -- pooling would have overstated format's
    # real accuracy at this band), not the old invented 0.95, and it
    # clears the gate via the explicit `auto_apply` override (Hansel's
    # F120 acceptance), not via the raw number.
    assert r.type.value == "eat" and r.type.auto_apply is True and r.type.confidence == pytest.approx(0.760)
    assert r.format.value == "review" and r.format.auto_apply is True and r.format.confidence == pytest.approx(0.560)
    assert r.subtype.value == "restaurant" and r.subtype.confidence >= 0.85  # subtype untouched by F120
    assert any(loc.value == "jakarta" and loc.confidence >= 0.85 for loc in r.locations)  # location untouched


# --- F106 finding 7 / F111 / F113: rules.mixed_categories ("the E2.0 value
# stays the prior unless the cue instrument gives it <= 10% support against
# >= 50% for the alternate") applied at classify-time to a category-fixed
# (non-per-article) facet, not only when an editor already flagged the
# category per-article. Measured against the 253-item human-adjudicated
# calibration set (see engine/packages/eval/data/calibration): net-neutral
# on `type` (kept enabled below), net-NEGATIVE on `format` (the `heritage`
# format cue over-fires on culture/history feature prose) -- so `format`'s
# category-fixed branch deliberately does NOT call this override; see the
# comment at its call site in resolve.py.

def test_mixed_categories_override_fires_at_the_stated_thresholds():
    # prior gets <=10% support, alternate gets >=50% -> override fires.
    value, note = _mixed_categories_override("editorial", {"editorial": 1.0, "eat": 9.0})
    assert value == "eat" and note is not None


def test_mixed_categories_override_does_not_fire_below_threshold():
    # alternate short of 50% support -> prior stays, per the pack's own rule.
    value, note = _mixed_categories_override("editorial", {"editorial": 3.0, "eat": 5.0})
    assert value == "editorial" and note is None


def test_mixed_categories_override_needs_both_conditions():
    # prior support well above 10% even though an alternate exists -> no override.
    value, note = _mixed_categories_override("editorial", {"editorial": 4.0, "eat": 6.0})
    assert value == "editorial" and note is None


def test_mixed_categories_override_no_op_without_signal():
    assert _mixed_categories_override(None, {"eat": 5.0}) == (None, None)
    assert _mixed_categories_override("editorial", {}) == ("editorial", None)
    assert _mixed_categories_override("editorial", {"editorial": 0.0, "eat": 0.0}) == ("editorial", None)


def test_category_fixed_type_can_be_overridden_by_strong_cue_evidence():
    # F106 finding 7's shape: a category fixes type=editorial, but the
    # per-article cue instrument gives it almost no support against a
    # dominant alternate -- type should flip; confidence stays category-fixed.
    a = _article(title="Sungai Watch's New Recycling Kitchen", text="A new eatery serving zero-waste meals.")
    res = _fixed_res(type="editorial", per_article=[])
    d10 = D10Result(res, "yoast_primary")
    features = {"type": None, "format": None, "type_scores": {"editorial": 0.3, "eat": 4.0}, "format_scores": {}}
    r = classify_article(a, d10, features, _terms())
    assert r.type.value == "eat"
    # F120 routing: still category_fixed_high -- routed to keyword_cue,
    # same measured confidence/auto_apply as the un-overridden case; only
    # the VALUE changed (mixed_categories_override fired upstream).
    assert r.type.auto_apply is True and r.type.confidence == pytest.approx(0.760)


def test_category_fixed_format_is_not_overridden_even_with_strong_cue_evidence():
    # Deliberately asymmetric with the type test above: format's category-fixed
    # branch does not call the override at all (measured net-negative -- see
    # the module comment), so format stays exactly at the category prior
    # regardless of what the cue instrument scores.
    a = _article(title="Some Review", text="A nice restaurant review.")
    res = _fixed_res(format="review")
    d10 = D10Result(res, "yoast_primary")
    features = {"type": None, "format": None, "type_scores": {}, "format_scores": {"review": 0.1, "heritage": 9.0}}
    r = classify_article(a, d10, features, _terms())
    assert r.format.value == "review"


def test_per_article_type_cue_confident_overrides_category_prior():
    a = _article(title="Best cocktail bar in town", text="We tried the cocktails.")
    res = _fixed_res(type=None, per_article=["type"])
    d10 = D10Result(res, "deepest_child")
    features = {"type": "drink", "type_margin": 3.0, "format": None, "format_scores": {}}
    r = classify_article(a, d10, features, _terms())
    # F120 routing: margin >= 2.0 -> cue_confident band -> routes to
    # embeddings_centroid. No vector/centroid_models supplied here, so
    # this ABSTAINS (deliberately -- no invented number, no auto-apply
    # without real evidence) rather than falling back to the old invented
    # CUE_CONFIDENT=0.93. Value still comes from the cue (the abstain
    # fallback), but it now goes to review. See test_embed_routing.py for
    # the routed (non-abstaining, auto-applying) path with a real vector.
    assert r.type.value == "drink"
    assert r.type.auto_apply is False
    assert r.type.confidence < 0.85


def test_per_article_type_cue_abstain_falls_back_to_category_prior_below_gate():
    res = _fixed_res(type=None, per_article=["type"])
    a = _article(title="A quiet afternoon", text="Nothing much happened.")
    d10 = D10Result(res, "deepest_child")
    features = {"type": None, "type_margin": 0.0, "type_scores": {}, "format": None, "format_scores": {}}
    r = classify_article(a, d10, features, _terms())
    assert r.type.confidence < 0.85  # abstain fallback never auto-applies


def test_title_and_lead_only_location_hits_both_auto_apply_post_f113():
    """Historical note this test used to guard against: 'siomay bandung' /
    'nasi bali' are DISH names that can appear in a lead paragraph without
    being real location references (found live on wp_id 5557), which is
    why `lead_only_match` originally shipped deliberately UNDER the gate
    (invented 0.55). F113 measured it directly against 17 real adjudicated
    disagreements and found it correct 17/17 (1.00) -- the dish-name
    false-positive concern was real motivation but not, in measured fact,
    a frequent error, so F117 promoted this mechanism, and F120's
    permanent fix (confidence.py) keeps it promoted on every future
    re-run. Both title and lead-only hits now clear the gate -- on their
    OWN, independently measured accuracy (0.97 vs 1.00), not the same
    invented number."""
    res = _fixed_res(location="jakarta")
    a = _article(title="Kristal Hotel Launches Sunday Street Food Brunch",
                 text="You can eat nasi bali and siomay bandung at the buffet.")
    d10 = D10Result(res, "deepest_child")
    features = {"type": None, "format": None, "type_scores": {}, "format_scores": {}}
    r = classify_article(a, d10, features, _terms(), title_location_hits=[], lead_only_location_hits=["bali", "bandung"])
    by_slug = {loc.value: loc for loc in r.locations}
    assert by_slug["jakarta"].confidence >= 0.85  # category-fixed location still applies
    assert by_slug["bali"].confidence == pytest.approx(1.00)
    assert by_slug["bandung"].confidence == pytest.approx(1.00)


def test_site_home_fallback_when_no_fixed_location_and_no_title_hit():
    res = _fixed_res(location=None, per_article=["location"])
    a = _article(city="jakarta", title="Untitled", text="No place mentioned.")
    d10 = D10Result(res, "deepest_child")
    features = {"type": None, "format": None, "type_scores": {}, "format_scores": {}}
    r = classify_article(a, d10, features, _terms(), title_location_hits=[], lead_only_location_hits=[])
    assert len(r.locations) == 1
    assert r.locations[0].value == "jakarta"
    assert r.locations[0].confidence >= 0.85


def test_f104_title_match_does_not_displace_a_co_filed_categorys_fixed_location():
    """Regression for F104: Jakarta wp_ids 87586/88356/90002/91372/93158
    ("Amber Lombok Beach Resort") carry categories=['Bali Updates'] (fixes
    location=bali), but D10 resolved type/subtype/format via a DIFFERENT
    co-filed category ('Explore Indonesia', a parent container whose own
    proposal fixes no location -- location=None, per_article=['location']).
    Before the fix, `classify_article` only ever consulted the single D10
    winner for a fixed location, so 'bali' was silently dropped entirely and
    a title match on 'lombok' became the article's only location -- not
    applied, not gated, not queued, no trace. `location` is multi-cardinality
    (rules.location), so the correct output is *both* bali and lombok."""
    d10_category = _fixed_res(
        type="editorial", subtype=None, format="city-guide", location=None,
        per_article=["location"],
    )
    d10_category.name = "Explore Indonesia"
    d10 = D10Result(d10_category, "yoast_primary")
    # The OTHER category this article is filed under (not the D10 winner)
    # independently fixes location=bali at "high" confidence.
    category_fixed_locations = [("bali", "high", "Bali Updates")]
    a = _article(title="Amber Lombok Beach Resort", categories=["Bali Updates"],
                 text="Amber Lombok Beach Resort offers stunning views.")
    features = {"type": None, "format": None, "type_scores": {}, "format_scores": {}}
    r = classify_article(a, d10, features, _terms(), title_location_hits=["bandung"],
                          lead_only_location_hits=[], category_fixed_locations=category_fixed_locations)
    by_slug = {loc.value: loc for loc in r.locations}
    assert by_slug["bali"].confidence >= 0.85 and by_slug["bali"].source == "inferred"
    assert by_slug["bandung"].confidence == pytest.approx(0.97) and by_slug["bandung"].source == "ai"
    assert "jakarta" not in by_slug  # no site-home fallback: a real fixed location was found


def test_f104_merge_picks_the_numerically_stronger_of_title_hit_vs_category_fix():
    """If a co-filed category's fixed location happens to share a slug with
    a title hit, the numerically STRONGER of the two must win, not
    whichever was merged last (guards the `existing is None or other_conf
    > existing.confidence` ordering check added for F104). F113's measured
    numbers changed which one that is for `medium` specifically --
    `category_fixed_medium` measured 1.00 (a PERFECT small sample),
    actually more reliable than `title_match`'s own 0.97 -- so this is
    deliberately no longer "title always wins"; it is "whichever measured
    higher wins", tested both ways below."""
    d10_category = _fixed_res(type="editorial", subtype=None, format="city-guide", location=None,
                               per_article=["location"])
    d10_category.name = "Container"
    d10 = D10Result(d10_category, "yoast_primary")
    features = {"type": None, "format": None, "type_scores": {}, "format_scores": {}}

    # category_fixed_medium (1.00) now beats title_match (0.97).
    a = _article(title="Bali", categories=["Some Category"], text="")
    r = classify_article(a, d10, features, _terms(), title_location_hits=["bali"],
                          lead_only_location_hits=[],
                          category_fixed_locations=[("bali", "medium", "Some Category")])
    by_slug = {loc.value: loc for loc in r.locations}
    assert by_slug["bali"].confidence == pytest.approx(1.00)

    # category_fixed_high (0.86) still loses to title_match (0.97) --
    # confirms the merge is a real numeric comparison, not a hardcoded
    # "category always wins now" flip.
    a2 = _article(title="Bali", categories=["Some Other Category"], text="")
    r2 = classify_article(a2, d10, features, _terms(), title_location_hits=["bali"],
                           lead_only_location_hits=[],
                           category_fixed_locations=[("bali", "high", "Some Other Category")])
    by_slug2 = {loc.value: loc for loc in r2.locations}
    assert by_slug2["bali"].confidence == pytest.approx(0.97)


def test_no_category_resolution_still_produces_a_full_result():
    a = _article(title="Random uncategorized post", text="")
    d10 = D10Result(None, "none")
    features = {"type": None, "format": None, "type_scores": {}, "format_scores": {}}
    r = classify_article(a, d10, features, _terms())
    assert r.type.value is not None  # never a silent None -- 'unknown' at worst
    assert r.format.value is not None
    assert len(r.locations) >= 1  # site_home_fallback guarantees at least one
    assert r.type.confidence < 0.85  # never fact-written without real evidence


# --- F120 routing: cue_confident/cue_fired bands route to the embeddings
# centroid instrument when a real article vector + centroid model are
# available (see embed_routing.py / test_embed_routing.py for the routing
# logic itself; these are the resolve.py wiring tests).

def _centroid_model():
    from now_classifier.embed_routing import CentroidModel
    return CentroidModel(
        facet="type",
        centroids={"drink": [1.0, 0.0], "eat": [0.0, 1.0]},
        class_n={"drink": 10, "eat": 10},
        excluded_classes=frozenset(),
        min_class_n=5,
    )


def test_per_article_cue_confident_routes_to_embeddings_when_vector_available():
    a = _article(title="Best cocktail bar in town", text="We tried the cocktails.")
    res = _fixed_res(type=None, per_article=["type"])
    d10 = D10Result(res, "deepest_child")
    # cue proposes "drink" with margin 3.0 (>= 2.0 -> cue_confident band);
    # the article vector is nearest the "eat" centroid, so a real routed
    # decision must FLIP the value to what embeddings predicts, not keep
    # the cue's "drink".
    features = {"type": "drink", "type_margin": 3.0, "format": None, "format_scores": {}}
    r = classify_article(a, d10, features, _terms(), article_vector=[0.1, 0.9],
                          centroid_models={"type": _centroid_model()})
    assert r.type.value == "eat"
    assert r.type.auto_apply is True
    assert r.type.confidence == pytest.approx(0.840)  # type-specific, not the pooled 0.78
    assert r.type.source == "ai"
    assert "embeddings_centroid" in r.type.reasoning


def test_per_article_cue_fired_routes_to_embeddings_at_its_own_measured_accuracy():
    a = _article(title="A drink somewhere", text="Some cocktails maybe.")
    res = _fixed_res(type=None, per_article=["type"])
    d10 = D10Result(res, "deepest_child")
    features = {"type": "drink", "type_margin": 0.5, "format": None, "format_scores": {}}  # < 2.0 -> cue_fired
    r = classify_article(a, d10, features, _terms(), article_vector=[1.0, 0.0],
                          centroid_models={"type": _centroid_model()})
    assert r.type.value == "drink"
    assert r.type.auto_apply is True
    assert r.type.confidence == pytest.approx(0.667)  # type-specific, not the pooled 0.53


def test_category_fixed_high_routes_to_keyword_cue_at_its_measured_accuracy():
    """category_fixed_high (0.95) routes to keyword_cue/category prior, not
    embeddings -- F120 measured the cue instrument winning there for both
    facets (type 0.760 vs centroid 0.680; format 0.560 vs centroid 0.340).
    Supplying a centroid model must NOT change the value or route it
    through embeddings."""
    a = _article(title="Some Review", text="A nice restaurant review.")
    res = _fixed_res()
    d10 = D10Result(res, "yoast_primary")
    r = classify_article(a, d10, {"type": None, "format": None, "type_scores": {}, "format_scores": {}},
                          _terms(), article_vector=[0.1, 0.9], centroid_models={"type": _centroid_model()})
    assert r.type.value == "eat"  # unchanged by the (irrelevant) centroid
    assert r.type.auto_apply is True
    assert r.type.confidence == pytest.approx(0.760)
    assert "keyword_cue" in r.type.reasoning


def test_embeddings_routed_band_abstains_on_a_thin_excluded_class():
    """F120: a class with too few labelled exemplars (e.g. `wellness`=2,
    `shop`=3 for `type`) is excluded from centroid candidacy entirely --
    when the model has NO trusted classes at all for a facet, every
    article for that facet must abstain (fall back to the cue's own value,
    review-gated), never force a prediction from an empty candidate set."""
    from now_classifier.embed_routing import CentroidModel
    empty_model = CentroidModel(facet="type", centroids={}, class_n={"wellness": 2}, excluded_classes=frozenset({"wellness"}), min_class_n=5)
    a = _article(title="Best cocktail bar in town", text="We tried the cocktails.")
    res = _fixed_res(type=None, per_article=["type"])
    d10 = D10Result(res, "deepest_child")
    features = {"type": "drink", "type_margin": 3.0, "format": None, "format_scores": {}}
    r = classify_article(a, d10, features, _terms(), article_vector=[0.1, 0.9],
                          centroid_models={"type": empty_model})
    assert r.type.auto_apply is False
    assert r.type.confidence < 0.85
    assert r.type.value == "drink"  # cue's own value, not silently replaced
