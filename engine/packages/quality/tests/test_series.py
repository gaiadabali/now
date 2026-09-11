from now_quality.series import (
    ArticleRow,
    cluster_titles,
    find_fuzzy_candidates,
    normalize_title,
    pick_current,
)


def test_normalize_strips_year_and_updated_marker():
    a = normalize_title("New Restaurants in Jakarta 2024: Latest Openings [Updated]")
    b = normalize_title("New Restaurants in Jakarta 2025: Latest Openings [Updated]")
    assert a == b


def test_normalize_survives_mangled_apostrophe_and_missing_space():
    # The corpus's real third candidate: "NOW! Jakarta's ..." vs
    # "NOW!Jakarta<mangled>s ..." (a corrupted right-single-quote + a
    # dropped space before "Jakarta").
    a = normalize_title("NOW! Jakarta's Best Restaurant, Bar and Cafe Awards 2016")
    b = normalize_title("NOW!Jakarta�s Best Restaurant, Bar and Cafe Awards 2018")
    assert a == b


def test_normalize_decodes_html_entities():
    a = normalize_title("Hilltop Getaway at The Botanica Sanctuary &amp; Pesona Alam 2024")
    b = normalize_title("Hilltop Getaway at The Botanica Sanctuary & Pesona Alam 2025")
    assert a == b


def test_confident_series_clustered_with_year_variation():
    rows = [
        ArticleRow(1, "ArtMoments Jakarta 2023", "2023-07-28"),
        ArticleRow(2, "ArtMoments Jakarta 2024", "2024-08-01"),
    ]
    report = cluster_titles(rows)
    assert len(report.confident) == 1
    assert len(report.uncertain) == 0
    cluster = report.confident[0]
    assert cluster.series_key == "artmoments-jakarta"
    assert cluster.current_id == 2  # 2024 > 2023


def test_three_member_series_current_is_highest_year():
    rows = [
        ArticleRow(1, "New Restaurants in Jakarta 2024: Latest Openings [Updated]", "2025-01-07"),
        ArticleRow(2, "New Restaurants in Jakarta 2025: Latest Openings [Updated]", "2025-11-12"),
        ArticleRow(3, "New Restaurants in Jakarta 2026: Latest Openings [Updated]", "2026-08-26"),
    ]
    report = cluster_titles(rows)
    assert len(report.confident) == 1
    assert report.confident[0].current_id == 3


def test_identical_titles_no_year_signal_are_flagged_uncertain_not_merged():
    rows = [
        ArticleRow(10, "An Interview with H.E. Patrick Herman, Ambassador of Belgium to Indonesia", "2019-01-04"),
        ArticleRow(11, "An Interview with H.E. Patrick Herman, Ambassador of Belgium to Indonesia", "2019-01-04"),
    ]
    report = cluster_titles(rows)
    assert len(report.confident) == 0
    assert len(report.uncertain) == 1


def test_singletons_are_not_clustered():
    rows = [
        ArticleRow(1, "A Totally Unique Title", "2024-01-01"),
        ArticleRow(2, "Another Completely Different Title", "2024-01-02"),
    ]
    report = cluster_titles(rows)
    assert report.confident == []
    assert report.uncertain == []


def test_existing_series_key_is_extended_not_forked():
    rows = [
        ArticleRow(1, "ArtMoments Jakarta 2023", "2023-07-28", existing_series_key="artmoments-jakarta"),
        ArticleRow(2, "ArtMoments Jakarta 2024", "2024-08-01", existing_series_key=None),
    ]
    report = cluster_titles(rows)
    assert report.confident[0].series_key == "artmoments-jakarta"


def test_conflicting_existing_keys_are_flagged_not_resolved():
    rows = [
        ArticleRow(1, "ArtMoments Jakarta 2023", "2023-07-28", existing_series_key="artmoments-jakarta"),
        ArticleRow(2, "ArtMoments Jakarta 2024", "2024-08-01", existing_series_key="some-other-key"),
    ]
    report = cluster_titles(rows)
    assert report.confident == []
    assert len(report.uncertain) == 1
    assert "conflicting" in report.uncertain[0].series_key


def test_unrelated_articles_that_merely_share_common_words_do_not_cluster():
    rows = [
        ArticleRow(1, "Best Padel Courts in Jakarta", "2024-01-01"),
        ArticleRow(2, "Best Museums in Jakarta", "2024-01-02"),
        ArticleRow(3, "Best Spas in Jakarta", "2024-01-03"),
    ]
    report = cluster_titles(rows)
    assert report.confident == []
    assert report.uncertain == []


def test_pick_current_falls_back_to_latest_published_when_no_years():
    rows = [
        ArticleRow(1, "Some Guide [Updated]", "2024-01-01"),
        ArticleRow(2, "Some Guide [Updated]", "2025-06-01"),
    ]
    assert pick_current(rows).id == 2


def test_fuzzy_candidates_do_not_include_already_grouped_norms():
    rows = [
        ArticleRow(1, "ArtMoments Jakarta 2023", "2023-07-28"),
        ArticleRow(2, "ArtMoments Jakarta 2024", "2024-08-01"),
    ]
    already_grouped = {normalize_title("ArtMoments Jakarta 2023")}
    candidates = find_fuzzy_candidates(rows, already_grouped)
    assert candidates == []
