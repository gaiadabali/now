from now_taxonomy_evidence.sources import Article, Category

from now_classifier.review_doc import CategoryResolution, ReviewDoc, resolve_article_category


def _article(**kw):
    base = dict(city="jakarta", wp_id=1, title="t", slug="t", date="2019-01-01",
                categories=[], primary_category_id=None, excerpt="", text="", focus_kw=None, views=None)
    base.update(kw)
    return Article(**base)


def _cat(name, term_id, parent_name=None, published=1):
    return Category(city="jakarta", name=name, slug=name.lower(), term_id=term_id,
                     parent_id=None, parent_name=parent_name, description="", wp_count=published,
                     published=published)


def _res(term_id, name, container=False, confidence="high"):
    return CategoryResolution(term_id=term_id, name=name, slug=name.lower(), container=container,
                               confidence=confidence, reasoning="", proposal={"type": "eat"}, decisions=[])


def _doc(resolutions):
    return ReviewDoc(city="jakarta", rules={}, by_term_id={r.term_id: r for r in resolutions}, raw={})


def test_yoast_primary_wins_even_with_other_categories():
    a = _article(primary_category_id=42, categories=["Dining Offers", "Events"])
    cats_by_name = {"Dining Offers": _cat("Dining Offers", 42), "Events": _cat("Events", 99)}
    review = _doc([_res(42, "Dining Offers"), _res(99, "Events")])
    result = resolve_article_category(a, cats_by_name, review)
    assert result.method == "yoast_primary"
    assert result.resolution.name == "Dining Offers"


def test_deepest_child_prefers_non_container_over_container():
    a = _article(primary_category_id=None, categories=["Dining", "Reviews"])
    cats_by_name = {
        "Dining": _cat("Dining", 1, parent_name=None),
        "Reviews": _cat("Reviews", 2, parent_name="Dining"),
    }
    review = _doc([_res(1, "Dining", container=True), _res(2, "Reviews", container=False)])
    result = resolve_article_category(a, cats_by_name, review)
    assert result.method == "deepest_child"
    assert result.resolution.name == "Reviews"
    assert result.ambiguous is False


def test_parent_container_fallback_when_every_candidate_is_a_container():
    a = _article(primary_category_id=None, categories=["Lifestyle", "Culture"])
    cats_by_name = {"Lifestyle": _cat("Lifestyle", 5), "Culture": _cat("Culture", 6, published=3)}
    review = _doc([_res(5, "Lifestyle", container=True), _res(6, "Culture", container=True)])
    result = resolve_article_category(a, cats_by_name, review)
    assert result.method == "parent_container"
    # deterministic: smallest published count wins (Lifestyle=1 < Culture=3)
    assert result.resolution.name == "Lifestyle"


def test_ambiguous_tiebreak_is_flagged_and_deterministic():
    a = _article(primary_category_id=None, categories=["Bars", "Cafes"])
    cats_by_name = {
        "Bars": _cat("Bars", 10, parent_name="Dining", published=50),
        "Cafes": _cat("Cafes", 11, parent_name="Dining", published=5),
    }
    review = _doc([_res(10, "Bars", container=False), _res(11, "Cafes", container=False)])
    result = resolve_article_category(a, cats_by_name, review)
    assert result.method == "deepest_child"
    assert result.ambiguous is True
    assert result.resolution.name == "Cafes"  # rarer (smaller published count) wins the tiebreak


def test_no_matching_category_returns_none():
    a = _article(primary_category_id=None, categories=["Unmapped"])
    result = resolve_article_category(a, {}, _doc([]))
    assert result.method == "none"
    assert result.resolution is None
