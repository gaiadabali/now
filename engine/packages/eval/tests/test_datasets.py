"""Dataset-builder tests against a small synthetic fixture
(tests/fixtures/articles_sample.jsonl + taxonomy_mapping_sample.json)
independent of the real archive, so these assertions are hand-derivable
and don't shift if the real corpus changes.

Fixture layout (see fixtures/articles_sample.jsonl, generated
deterministically -- wp_id 1000-1039):
  wp 1000-1011  category "Dining News"          (12, primary_category=1)
  wp 1012-1023  category "Events"                (12, primary_category=2)
  wp 1024-1031  category "News"                  (8,  primary_category=3)
  wp 1032-1036  category "A Jakarta Smorgasbord" (5,  primary_category=4, is_print_issue)
  wp 1037-1039  category "Small Category"        (3,  primary_category=5, too small for related-articles)

With the package's default split (salt "now-eval-split-v1", 20%), the
eval-split wp_ids in this exact range are:
  {1010, 1019, 1021, 1022, 1029, 1031, 1032, 1033, 1036, 1037, 1038}
(verified directly via `split.is_eval` in test_split_membership_matches_fixture_assumptions
below -- every other test in this file depends on that set being correct,
so if that assertion ever fails, the split hash or salt changed and
every count below must be re-derived, not patched around.)
"""
from now_eval.datasets.split import is_eval
from now_eval.datasets.sources import load_articles, load_category_priors
from now_eval.datasets.related_articles import build_related_articles_labels
from now_eval.datasets.type_labels import build_type_labels
from now_eval.datasets.facet_labels import build_facet_labels, slugify

EXPECTED_EVAL_WP_IDS = {1010, 1019, 1021, 1022, 1029, 1031, 1032, 1033, 1036, 1037, 1038}


def test_split_membership_matches_fixture_assumptions():
    actual = {wp_id for wp_id in range(1000, 1040) if is_eval(wp_id)}
    assert actual == EXPECTED_EVAL_WP_IDS


def test_load_articles_and_priors(articles_sample_path, taxonomy_sample_path):
    articles = load_articles(articles_sample_path)
    assert len(articles) == 40
    priors = load_category_priors(taxonomy_sample_path)
    assert priors["Dining News"].type_ == "eat"
    assert priors["Dining News"].type_is_category_certain is True
    assert priors["News"].type_ is None
    assert priors["News"].type_is_category_certain is False
    # Print-issue category has a HIGH-confidence, non-per-article type
    # prior (editorial) but must still be excluded by the print-issue guard.
    assert priors["A Jakarta Smorgasbord"].is_print_issue is True
    assert priors["A Jakarta Smorgasbord"].type_is_category_certain is False


def test_type_labels_pool_matches_hand_derivation(articles_sample_path, taxonomy_sample_path):
    # Qualifying eval-split articles: 1010 (Dining News -> eat),
    # 1019/1021/1022 (Events -> event), 1037/1038 (Small Category -> do).
    # News doesn't qualify (type is null); print-issue is excluded even
    # though its category-level type prior is HIGH confidence.
    labels = build_type_labels(articles_sample_path, taxonomy_sample_path)
    got = {(l.wp_id, l.type) for l in labels}
    assert got == {
        (1010, "eat"),
        (1019, "event"),
        (1021, "event"),
        (1022, "event"),
        (1037, "do"),
        (1038, "do"),
    }
    assert all(l.label_provenance == "category_prior_high_confidence_not_human_reviewed" for l in labels)


def test_type_labels_respects_max_per_type_cap(articles_sample_path, taxonomy_sample_path):
    labels = build_type_labels(articles_sample_path, taxonomy_sample_path, max_per_type=1)
    by_type: dict[str, int] = {}
    for l in labels:
        by_type[l.type] = by_type.get(l.type, 0) + 1
    assert all(count <= 1 for count in by_type.values())


def test_type_labels_sample_size_trim_preserves_small_groups(articles_sample_path, taxonomy_sample_path):
    # eat:1, event:3, do:2 = 6 total. Ask for sample_size=4: the trim
    # must shrink the largest group (event) first, never touching the
    # single-member 'eat' group down to zero while 'event' still has 2+.
    labels = build_type_labels(articles_sample_path, taxonomy_sample_path, sample_size=4)
    assert len(labels) == 4
    by_type: dict[str, int] = {}
    for l in labels:
        by_type[l.type] = by_type.get(l.type, 0) + 1
    assert by_type.get("eat", 0) == 1  # never squeezed out
    assert by_type.get("event", 0) <= 3


def test_related_articles_excludes_print_issue_and_small_categories(articles_sample_path, taxonomy_sample_path):
    queries = build_related_articles_labels(articles_sample_path, taxonomy_sample_path, min_category_size=8)
    seed_wp_ids = {q.seed_wp_id for q in queries}
    # Only Dining News / Events / News eval-split members qualify.
    assert seed_wp_ids == {1010, 1019, 1021, 1022, 1029, 1031}
    # None from the print-issue category or the too-small category.
    assert seed_wp_ids.isdisjoint({1032, 1033, 1036, 1037, 1038})


def test_related_articles_relevant_set_is_same_category_minus_self(articles_sample_path, taxonomy_sample_path):
    queries = build_related_articles_labels(articles_sample_path, taxonomy_sample_path, min_category_size=8)
    seed_1010 = next(q for q in queries if q.seed_wp_id == 1010)
    assert seed_1010.primary_category_name == "Dining News"
    # Dining News has 12 members; relevant set = other 11, and must not
    # include the seed itself.
    assert len(seed_1010.relevant_article_ids) == 11
    assert seed_1010.seed_article_id not in seed_1010.relevant_article_ids
    assert seed_1010.seed_article_id == "wp:1010"
    assert "wp:1000" in seed_1010.relevant_article_ids


def test_related_articles_sample_size_cap(articles_sample_path, taxonomy_sample_path):
    queries = build_related_articles_labels(
        articles_sample_path, taxonomy_sample_path, min_category_size=8, sample_size=2
    )
    assert len(queries) == 2


def test_facet_labels_only_eval_split_with_focus_keyword(articles_sample_path):
    # Hand-derived (see module docstring): only wp 1032, 1036 (print
    # issue) and 1037, 1038 (small category) have a focus keyword AND
    # fall in the eval split.
    labels = build_facet_labels(articles_sample_path)
    got_ids = {l.wp_id for l in labels}
    assert got_ids == {1032, 1036, 1037, 1038}


def test_facet_labels_are_slugified(articles_sample_path):
    labels = build_facet_labels(articles_sample_path)
    by_id = {l.wp_id: l for l in labels}
    label_1037 = by_id[1037]
    assert label_1037.focus_keyword_raw == "Small Category Topic 0"
    assert label_1037.facet_labels == ("small-category-topic-0",)


def test_slugify_hand_cases():
    assert slugify("Rooftop Bar") == "rooftop-bar"
    assert slugify("  Clarissa Goenawan  ") == "clarissa-goenawan"
    assert slugify("Ondel-Ondel") == "ondel-ondel"
    assert slugify("") == ""
    assert slugify("!!!") == ""
