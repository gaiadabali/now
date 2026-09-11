from now_geocode.dedupe import build_candidates
from now_geocode.pipeline import run
from now_geocode.report import render_markdown


def test_report_renders_key_sections():
    venues = [
        {"wp_id": 1, "name": "Resolved via seed", "status": "publish"},
        {"wp_id": 2, "name": "Unresolved thing", "status": "publish", "city": "Sanur"},
    ]
    geo = [
        {"source": "mappress", "wp_id": 3, "map_id": 1, "title": "Resolved via seed",
         "address": None, "lat": -8.69, "lng": 115.26}
    ]
    places, stats = run(venues, geo, provider=None)
    md = render_markdown(places, stats)
    assert "# E2.5 geocoding" in md
    assert "Resolution by source" in md
    assert "Confidence distribution" in md
    assert "Area-term assignment method" in md
    assert "Review queue" in md
    assert "Unresolved thing" in md
