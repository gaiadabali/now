from now_geocode.providers.offline import OfflineProvider
from now_geocode.quality import in_indonesia_bbox


def test_deterministic_across_calls():
    p = OfflineProvider()
    r1 = p.geocode_address("Jl. Test No 1, Seminyak, Bali")
    r2 = p.geocode_address("Jl. Test No 1, Seminyak, Bali")
    assert (r1.lat, r1.lng) == (r2.lat, r2.lng)


def test_different_input_different_point():
    p = OfflineProvider()
    r1 = p.geocode_address("Address One, Bali")
    r2 = p.geocode_address("Address Two, Bali")
    assert (r1.lat, r1.lng) != (r2.lat, r2.lng)


def test_always_marked_synthetic():
    p = OfflineProvider()
    assert p.geocode_address("Anywhere, Jakarta").is_synthetic is True
    assert p.find_place("Some Place", "Jakarta").is_synthetic is True


def test_stays_within_indonesia_bbox():
    p = OfflineProvider()
    for text in ["Bali venue", "Jakarta venue", "Unspecified venue"]:
        r = p.geocode_address(text)
        assert in_indonesia_bbox(r.lat, r.lng), f"{text} -> {r.lat},{r.lng}"


def test_empty_input_returns_none():
    p = OfflineProvider()
    assert p.geocode_address("") is None
    assert p.geocode_address(None) is None
    assert p.find_place("", None) is None
