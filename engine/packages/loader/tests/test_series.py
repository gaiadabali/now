from now_loader.series import derive_series_keys


def test_no_year_no_key():
    titles = {1: "ACG School Jakarta Provides the Right Start to Education"}
    assert derive_series_keys(titles) == {}


def test_singleton_year_title_gets_no_key():
    """A title that happens to end in a year but has no sibling must not
    become a lonely cluster of one."""
    titles = {1: "Jakarta Marathon 2023"}
    assert derive_series_keys(titles) == {}


def test_recurring_series_clusters():
    titles = {
        1: "New Restaurants in Jakarta 2024: Latest Openings [Updated]",
        2: "New Restaurants in Jakarta 2025: Latest Openings [Updated]",
        3: "New Restaurants in Jakarta 2026: Latest Openings [Updated]",
        4: "Completely Unrelated Article",
    }
    result = derive_series_keys(titles)
    assert set(result.keys()) == {1, 2, 3}
    assert len({result[1], result[2], result[3]}) == 1  # all same key
    assert 4 not in result


def test_year_without_updated_marker_still_clusters():
    titles = {1: "ArtMoments Jakarta 2023", 2: "ArtMoments Jakarta 2024"}
    result = derive_series_keys(titles)
    assert result[1] == result[2]
