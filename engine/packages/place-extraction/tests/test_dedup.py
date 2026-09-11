from now_place_extraction.dedup import cluster_candidates


def test_name_drift_variants_auto_merge():
    counts = {
        "The Ritz-Carlton Jakarta Mega Kuningan": 5,
        "Ritz Carlton Mega Kuningan": 3,
        "RC Jakarta": 1,
    }
    result = cluster_candidates(counts)
    # "RC Jakarta" is too dissimilar deterministically to merge automatically
    # (this is the ticket's own worked example of the hard case) -- it must
    # NOT be silently merged; it either stays its own singleton cluster or
    # shows up as a review pair, never a guessed auto-merge.
    merged_clusters = [c for c in result.clusters if len(c.members) > 1]
    assert any(
        "The Ritz-Carlton Jakarta Mega Kuningan" in c.members and "Ritz Carlton Mega Kuningan" in c.members
        for c in merged_clusters
    )
    rc_cluster = next(c for c in result.clusters if "RC Jakarta" in c.members)
    assert rc_cluster.members == ["RC Jakarta"]


def test_distinct_venues_never_merge_even_with_shared_brand_word():
    counts = {"Padma Resort Ubud": 4, "Padma Resort Legian": 3}
    result = cluster_candidates(counts)
    assert len(result.clusters) == 2
    assert all(len(c.members) == 1 for c in result.clusters)


def test_llm_adjudicate_only_called_on_ambiguous_band():
    calls = []

    def fake_llm(a, b):
        calls.append((a, b))
        return True

    # Deliberately identical after normalization -> auto-merge tier, LLM
    # must not be consulted for something the deterministic gate already
    # resolved.
    cluster_candidates({"Metis Lounge": 2, "METIS Lounge": 2}, llm_adjudicate=fake_llm)
    assert calls == []


def test_grand_suite_and_grand_club_do_not_over_merge():
    # Found live in the real Bali corpus: "Grand Suite", "Grand Club",
    # "Grand Club Lounge", "Grand Suites", "The Grand Bali Beach" and "The
    # Grand Club" were all merged into one cluster by the old rule --
    # a room type, a membership tier, and an unrelated hotel are not the
    # same venue just because they share the word "Grand".
    counts = {
        "Grand Suite": 8,
        "Grand Club": 5,
        "The Grand Bali Beach": 3,
    }
    result = cluster_candidates(counts)
    assert len(result.clusters) == 3, [c.members for c in result.clusters]


def test_canonical_name_is_most_frequent_surface_form():
    result = cluster_candidates({"Ritz Carlton Mega Kuningan": 1, "The Ritz-Carlton Jakarta Mega Kuningan": 9})
    cluster = result.clusters[0]
    assert cluster.canonical_name == "The Ritz-Carlton Jakarta Mega Kuningan"
