from now_partner_roster.cluster import DomainAgg, build_clusters


def _agg(netloc, link_count=1, articles=(1,), rel_none=None, rel_nofollow=0, rel_sponsored=0, dates=()):
    a = DomainAgg(netloc=netloc)
    a.link_count = link_count
    a.article_ids = set(articles)
    a.rel_none = link_count - rel_nofollow - rel_sponsored if rel_none is None else rel_none
    a.rel_nofollow = rel_nofollow
    a.rel_sponsored = rel_sponsored
    a.dates = list(dates)
    a.sample_articles = list(articles)[:8]
    return a


def test_merges_apex_domains_across_suffix_and_www():
    aggs = {
        "marriott.com": _agg("marriott.com", link_count=5, articles=(1, 2)),
        "marriott.co.id": _agg("marriott.co.id", link_count=2, articles=(3,)),
        "www.marriott.com": _agg("www.marriott.com", link_count=1, articles=(4,)),
    }
    rows = build_clusters(aggs)
    assert len(rows) == 1
    row = rows[0]
    assert row.org_slug == "marriott"
    assert row.link_count == 8
    assert row.article_count == 4
    assert sorted(row.domains) == ["marriott.co.id", "marriott.com"]
    assert row.parent_org_slug is None
    assert row.confidence >= 0.85  # marriott is in the canonical/well-known table


def test_subdomain_property_synthesizes_parent_when_apex_absent():
    aggs = {
        "bali.intercontinental.com": _agg("bali.intercontinental.com", link_count=10, articles=(1,)),
        "www.jakartapondokindah.intercontinental.com": _agg(
            "www.jakartapondokindah.intercontinental.com", link_count=5, articles=(2,)
        ),
    }
    rows = build_clusters(aggs)
    by_slug = {r.org_slug: r for r in rows}

    assert "intercontinental" in by_slug
    parent = by_slug["intercontinental"]
    assert parent.synthesized is True
    assert parent.link_count == 0
    assert parent.notes  # flagged for human review

    bali = by_slug["intercontinental-bali"]
    assert bali.parent_org_slug == "intercontinental"
    assert bali.link_count == 10
    assert not bali.synthesized

    jpi = by_slug["intercontinental-jakartapondokindah"]
    assert jpi.parent_org_slug == "intercontinental"
    # both children point at the SAME synthesized parent, not two separate ones
    assert jpi.parent_org_slug == bali.parent_org_slug


def test_subdomain_property_uses_real_apex_when_present():
    aggs = {
        "intercontinental.com": _agg("intercontinental.com", link_count=3, articles=(9,)),
        "bali.intercontinental.com": _agg("bali.intercontinental.com", link_count=10, articles=(1,)),
    }
    rows = build_clusters(aggs)
    by_slug = {r.org_slug: r for r in rows}
    parent = by_slug["intercontinental"]
    assert parent.synthesized is False
    assert parent.link_count == 3
    child = by_slug["intercontinental-bali"]
    assert child.parent_org_slug == "intercontinental"
    assert not child.notes  # real evidence, nothing ambiguous to flag


def test_rel_audit_aggregated_per_org():
    aggs = {
        "marriott.com": _agg("marriott.com", link_count=3, articles=(1,), rel_nofollow=1),
        "marriott.co.id": _agg("marriott.co.id", link_count=1, articles=(2,), rel_sponsored=1),
    }
    rows = build_clusters(aggs)
    row = rows[0]
    assert row.rel_audit == {"none": 2, "nofollow": 1, "sponsored": 1}


def test_unrelated_domain_stays_its_own_unmerged_org():
    aggs = {
        "davidmetcalfphotography.com": _agg("davidmetcalfphotography.com", link_count=4, articles=(1,)),
    }
    rows = build_clusters(aggs)
    assert len(rows) == 1
    assert rows[0].parent_org_slug is None
    assert rows[0].confidence < 0.85  # not in the well-known table, low-medium confidence only
