from now_eval.datasets.search_queries import build_provisional_query_set, load_gsc_queries


def test_provisional_query_set_sources_from_focus_keyword_and_title(articles_sample_path, taxonomy_sample_path):
    queries = build_provisional_query_set(articles_sample_path, taxonomy_sample_path, sample_size=20)
    sources = {q.source for q in queries}
    assert sources <= {"focus_keyword", "title"}
    assert len(queries) > 0


def test_provisional_query_seed_article_is_top_relevance(articles_sample_path, taxonomy_sample_path):
    queries = build_provisional_query_set(articles_sample_path, taxonomy_sample_path, sample_size=20)
    for q in queries:
        rel = q.relevance_map()
        # Every query must have at least one grade-3 (its own source
        # article) relevant doc -- otherwise the query has no "correct"
        # answer at all, which would make nDCG on it meaningless.
        assert 3.0 in rel.values()


def test_provisional_query_peers_are_weakly_relevant_not_equal_to_source(articles_sample_path, taxonomy_sample_path):
    queries = build_provisional_query_set(articles_sample_path, taxonomy_sample_path, sample_size=50)
    found_peer = False
    for q in queries:
        rel = q.relevance_map()
        for article_id, grade in rel.items():
            if grade == 1.0:
                found_peer = True
    assert found_peer, "expected at least one same-category peer graded 1.0 in this fixture"


def test_provisional_query_no_duplicate_source_articles(articles_sample_path, taxonomy_sample_path):
    queries = build_provisional_query_set(articles_sample_path, taxonomy_sample_path, sample_size=50)
    # Each query's "own" article (the grade-3 one) should be unique
    # across the set -- otherwise we'd double-count one article's signal.
    own_ids = []
    for q in queries:
        rel = q.relevance_map()
        own = [aid for aid, g in rel.items() if g == 3.0]
        own_ids.extend(own)
    assert len(own_ids) == len(set(own_ids))


def test_load_gsc_queries_hand_computed(gsc_export_sample_path, permalink_map_sample_path):
    labels = load_gsc_queries(gsc_export_sample_path, permalink_map_sample_path, min_clicks=1)
    by_query = {l.query: l.relevance_map() for l in labels}

    # "dining news topic": 2 pages both resolve via the permalink map.
    #   clicks=5  -> grade = min(3, 1+floor(log2(6))) = min(3, 1+2) = 3
    #   clicks=1  -> grade = min(3, 1+floor(log2(2))) = min(3, 1+1) = 2
    assert by_query["dining news topic"] == {"wp:1000": 3.0, "wp:1003": 2.0}

    # "events topic" has 0 clicks -> below min_clicks=1 -> omitted entirely
    # (not graded 0 -- 0 already means "not judged" elsewhere in this harness).
    assert "events topic" not in by_query

    # "unrelated query" resolves to a page with no permalink-map entry -> dropped.
    assert "unrelated query" not in by_query


def test_load_gsc_queries_respects_min_clicks_threshold(gsc_export_sample_path, permalink_map_sample_path):
    labels = load_gsc_queries(gsc_export_sample_path, permalink_map_sample_path, min_clicks=2)
    by_query = {l.query: l.relevance_map() for l in labels}
    # clicks=1 row for dining-news-3 must now be excluded.
    assert by_query["dining news topic"] == {"wp:1000": 3.0}
