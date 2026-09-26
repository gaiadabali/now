"""Pure tests for ranking, triage and dedupe planning -- no database."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from now_places.db import PlaceEvidence
from now_places.dedupe import plan_dedupe
from now_places.rank import evidence_score, featured_coverage, queue_order, recency
from now_places.region import region_verdict
from now_places.triage import triage

NOW = datetime(2026, 9, 26, tzinfo=timezone.utc)


def place(id: int, name: str, *, featured=0, articles=0, mentions=None, status="pending_review", source="extracted",
          newest=None, legacy=None, org=None, gpid=None, merged=None) -> PlaceEvidence:
    return PlaceEvidence(
        id=id, name=name, slug=f"p{id}", status=status, source=source, type="editorial", address=None,
        area_term=None, org_id=org, google_place_id=gpid, legacy_wp_id=legacy, merged_into_id=merged, aliases=None,
        featured=featured, mentions=mentions if mentions is not None else articles, articles=articles, newest=newest,
    )


# ------------------------------------------------------------------ rank

def test_score_worked_examples():
    """Pinned examples -- engine/apps/web/test/placeDesk.test.ts asserts the
    same numbers for the desk's SQL version of the score."""
    assert evidence_score(0, 0, False, None, now=NOW) == 0.0
    assert evidence_score(2, 5, False, None, now=NOW) == 11.0
    assert evidence_score(2, 5, True, None, now=NOW) == 13.0
    assert evidence_score(1, 1, False, NOW, now=NOW) == 5.0
    half = NOW - timedelta(days=1825 / 2)
    assert abs(evidence_score(1, 1, False, half, now=NOW) - 4.5) < 1e-9
    assert recency(NOW - timedelta(days=4000), now=NOW) == 0.0


def test_queue_is_score_then_featured_then_articles_then_id():
    rows = [place(3, "C", featured=1, articles=3), place(1, "A", featured=2, articles=0), place(2, "B", featured=1, articles=3)]
    ordered = [p.id for p, _ in queue_order(rows, now=NOW)]
    # A: 6, B: 6, C: 6 -> featured desc (A), then articles (B, C tie) then id
    assert ordered == [1, 2, 3]


def test_coverage_reports_both_denominators():
    rows = [place(1, "A", featured=5), place(2, "B", featured=3), place(3, "C", featured=2)]
    cov = featured_coverage(queue_order(rows, now=NOW), featured_total=12, top_n=2, featured_on_junk=2)
    assert cov.featured_in_top == 8
    assert abs(cov.share - 8 / 12) < 1e-9
    assert abs(cov.share_of_venues - 8 / 10) < 1e-9


# ---------------------------------------------------------------- triage

def test_triage_proposes_junk_only_on_pending_and_keeps_out_of_region_rows():
    rows = [
        place(1, "Hotel's", featured=4, articles=4),
        place(2, "Potato Head Beach Club", featured=3, articles=9),
        place(3, "Hotel's Pool", status="active"),  # junk-shaped but an editor approved it: left alone
        place(4, "InterContinental Bali Resort", featured=2, articles=5),  # a Bali venue in Jakarta's table
        place(5, "Already junk", status="junk"),
        place(6, "Merged row", merged=2),
    ]
    r = triage("jakarta", rows, featured_total=9, partnered=(set(), set()))
    assert [p.id for p in r.junk] == [1]
    assert [p.id for p in r.junk_skipped_not_pending] == [3]
    assert [p.id for p in r.out_of_region] == [4]
    assert 4 in [p.id for p, _ in r.queue]  # flagged, not removed
    assert 1 not in [p.id for p, _ in r.queue]
    assert r.already_decided == 1 and r.merged == 1
    assert r.coverage.featured_on_junk == 4


def test_partnership_term():
    rows = [place(1, "Alpha Cafe", articles=1, org="org-1"), place(2, "Beta Bistro", articles=1)]
    r = triage("bali", rows, featured_total=0, partnered=({"2"}, {"org-1"}))
    assert all(p.partnered for p in rows)
    r = triage("bali", [place(1, "Alpha Cafe")], featured_total=0, partnered=None)
    assert r.partnership_term == "unavailable"


def test_region_verdicts():
    assert region_verdict("jakarta", "InterContinental Bali Resort").out_of_region
    assert region_verdict("jakarta", "Karma Kandara Ungasan").region == "bali"
    assert not region_verdict("bali", "InterContinental Bali Resort").out_of_region
    assert not region_verdict("bali", "Potato Head Beach Club").out_of_region  # no signal at all
    assert region_verdict("bali", "Gaia Hotel Bandung").out_of_region
    assert not region_verdict("jakarta", "Hotel Indonesia Kempinski").out_of_region  # the country is not a region


# ---------------------------------------------------------------- dedupe

def test_high_score_pair_merges_into_the_better_row():
    rows = [
        place(10, "Karma Kandara Resort", featured=3, articles=10),
        place(11, "Karma Kandara", source="legacy_venue", legacy=501),
    ]
    plan = plan_dedupe("bali", rows)
    assert len(plan.merges) == 1
    op = plan.merges[0]
    assert (op.loser.id, op.survivor.id) == (10, 11)  # the legacy venue record survives
    assert op.score >= 0.85


def test_mid_band_pair_is_queued_never_merged():
    """P1.2's own acceptance: a 0.55-0.85 pair is queued, never merged."""
    rows = [place(20, "Padma Resort Ubud", articles=4), place(21, "Padma Resort Legian", articles=9)]
    plan = plan_dedupe("bali", rows)
    assert plan.merges == []
    assert len(plan.queued) == 1
    q = plan.queued[0]
    assert 0.55 <= q.score < 0.85
    assert q.why == "mid-band"


def test_guards_queue_high_scoring_pairs():
    # A hotel and its spa share the brand: different kinds of venue.
    rows = [place(30, "Spa Alila Seminyak", articles=5), place(31, "Alila Seminyak", articles=2)]
    plan = plan_dedupe("bali", rows)
    assert plan.merges == [] and plan.queued and plan.queued[0].why.startswith("only one name says")
    # Two separate legacy venue records.
    rows = [place(32, "Hotel Tugu Bali", legacy=1), place(33, "Tugu Hotel Bali", legacy=2)]
    plan = plan_dedupe("bali", rows)
    assert plan.merges == []
    # An approved duplicate is never merged away.
    rows = [place(34, "Green School", status="active"), place(35, "Green School Bali", status="active")]
    assert plan_dedupe("bali", rows).merges == []


def test_junk_rows_are_not_dedupe_candidates():
    rows = [place(40, "Hotel's"), place(41, "Hotel's"), place(42, "Maya Sanur")]
    plan = plan_dedupe("bali", rows)
    assert plan.candidates == 1 and plan.merges == []


def test_already_merged_rows_are_ignored():
    rows = [place(50, "Maya Sanur Resort", merged=51), place(51, "Maya Sanur")]
    assert plan_dedupe("bali", rows).merges == []
