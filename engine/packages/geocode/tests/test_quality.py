from now_geocode.quality import find_duplicate_centroids, in_indonesia_bbox


def test_bbox_accepts_known_jakarta_and_bali_points():
    assert in_indonesia_bbox(-6.2088, 106.8456)  # Jakarta
    assert in_indonesia_bbox(-8.4095, 115.1889)  # Bali


def test_bbox_rejects_same_named_street_elsewhere():
    # A geocoder with no country bias returning "Jakarta Street" in, say,
    # the Netherlands or the US would land far outside this box.
    assert not in_indonesia_bbox(52.37, 4.90)  # Amsterdam
    assert not in_indonesia_bbox(40.71, -74.01)  # New York


def test_duplicate_centroid_flags_distinct_places_sharing_a_point():
    resolved = [
        ("key1", "Venue A", -6.2, 106.8, "address_geocode"),
        ("key2", "Venue B", -6.2, 106.8, "address_geocode"),
        ("key3", "Venue C", -8.5, 115.2, "address_geocode"),
    ]
    groups = find_duplicate_centroids(resolved)
    assert len(groups) == 1
    assert groups[0].place_keys == ["key1", "key2"]


def test_existing_coordinates_repeat_alone_does_not_flag():
    # Two source rows for the *same* real venue (already merged upstream
    # in dedupe.py) sharing one free-seed coordinate is expected, not a
    # geocoder artifact — must not trigger the flag on its own.
    resolved = [
        ("key1", "Same Venue", -6.2, 106.8, "existing_coordinates"),
        ("key1", "Same Venue", -6.2, 106.8, "existing_coordinates"),
    ]
    assert find_duplicate_centroids(resolved) == []


def test_provider_result_colliding_with_existing_seed_still_flags():
    resolved = [
        ("key1", "Free Seed Venue", -6.2, 106.8, "existing_coordinates"),
        ("key2", "Geocoded Venue", -6.2, 106.8, "address_geocode"),
    ]
    groups = find_duplicate_centroids(resolved)
    assert len(groups) == 1
    assert set(groups[0].place_keys) == {"key1", "key2"}


def test_near_miss_does_not_flag():
    resolved = [
        ("key1", "Venue A", -6.20000, 106.80000, "address_geocode"),
        ("key2", "Venue B", -6.25000, 106.85000, "address_geocode"),
    ]
    assert find_duplicate_centroids(resolved) == []
