from pathlib import Path

from now_partner_roster.pipeline import iter_jsonl, run

FIXTURE = Path(__file__).parent / "fixtures" / "articles_sample.jsonl"


def _run():
    return run(iter_jsonl(FIXTURE))


def test_pipeline_over_fixture_counts():
    org_rows, exclusions, stats = _run()

    assert stats.articles == 7
    # uploads and mailto/tel are never counted as external links
    assert stats.total_upload_links == 1
    assert stats.total_non_http_links == 2  # mailto: + tel:

    by_slug = {r.org_slug: r for r in org_rows}
    assert "marriott" in by_slug
    marriott = by_slug["marriott"]
    # marriott.com (x2, one plain, one sponsored) + marriott.co.id (nofollow)
    assert marriott.link_count == 3
    assert marriott.rel_audit == {"none": 1, "nofollow": 1, "sponsored": 1}

    # the double-scheme copy/paste bug (http://https://...) must resolve to
    # its real domain, not vanish or show up as "https:"
    assert "doubledomain" in by_slug
    assert by_slug["doubledomain"].domains == ["doubledomain.com"]

    excluded_domains = {e.domain for e in exclusions}
    assert "www.instagram.com" in excluded_domains
    assert "unsplash.com" in excluded_domains
    assert "bit.ly" in excluded_domains
    assert "nowjakarta.co.id" in excluded_domains
    # the internal wp-content/uploads link on our own domain must never even
    # reach classification — it's dropped as an upload, not counted as excluded
    assert not any(
        "uploads" in d for d in excluded_domains
    )


def test_pipeline_is_idempotent():
    org_rows_a, exclusions_a, stats_a = _run()
    org_rows_b, exclusions_b, stats_b = _run()

    def _fingerprint(rows):
        return sorted((r.org_slug, r.link_count, r.article_count, r.parent_org_slug) for r in rows)

    assert _fingerprint(org_rows_a) == _fingerprint(org_rows_b)
    assert stats_a == stats_b


def test_intercontinental_property_from_fixture():
    org_rows, _, _ = _run()
    by_slug = {r.org_slug: r for r in org_rows}
    assert "intercontinental-bali" in by_slug
    bali = by_slug["intercontinental-bali"]
    assert bali.parent_org_slug == "intercontinental"
    parent = by_slug["intercontinental"]
    assert parent.synthesized is True
