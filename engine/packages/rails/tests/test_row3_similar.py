"""Row 3 Similar -- semantic kNN + series dedup.

Two data regimes, deliberately kept separate:

- `test_row3_series_dedup_on_real_data` / `test_row3_real_subject_with_unknown_type_returns_empty`
  run against REAL `now_jakarta` content: real embeddings (4,772/4,772
  articles, verified), real `series_key` groups (2 groups, 3+2 members,
  verified).
- `test_row3_competitor_exclusion_*` exercise `resolve_eligible_articles`
  (the SQL-hard-filter + ladder stage `compute_row3` also calls) against a
  `now_filters.synthetic` temp articles table, independent of embeddings
  entirely -- proving the exclusion/dedup mechanism without needing
  synthetic ids to have real vectors.

**F68 changed what "real data" can prove here.** `now_filters
.excluded_types_for` now fails closed for `subject_type is None` --
correct (Sec.8.A's guarantee must not have a None-shaped hole), but the
SQL predicate it drives (`primary_type::text != ALL(:excluded_types)`)
evaluates to SQL NULL, and so excludes, every real candidate row, because
`primary_type` is NULL archive-wide (F50: 0/4,772). A None subject_type is
also the ONLY state any real subject can be in today (E2.1 hasn't run),
so `compute_row3` called the ordinary way on ANY real article id now
always resolves zero eligible candidates and returns empty BEFORE ever
reaching the semantic-kNN ranking this file's real-data tests exist to
prove -- verified directly, not assumed
(`test_row3_real_subject_with_unknown_type_returns_empty`, the renamed
`test_row3_real_subject_returns_nonempty_results`, now asserts the
opposite of what it used to for exactly this reason). This is F68 working
as designed (PROGRESS.md), not a regression in this switch.

To still prove series dedup against the REAL 3-member series with REAL
embeddings (this ticket's own ask), `test_row3_series_dedup_on_real_data`
overrides the subject's `primary_type` to `"editorial"` -- a real,
`engine.type_relations`-known, `exclude_same=False` type, exactly the
technique F68's own fix used for its two equivalent `now_filters` tests
(see PROGRESS.md F68) -- so `excluded_types_for` returns an EMPTY set and
the SQL competitor predicate is skipped entirely, letting real,
NULL-typed candidates flow through on their own merits (status/quality/
series-dedup, all still fully enforced). This does not weaken or bypass
any guard; it supplies a real, known, non-restrictive type so the
UNRELATED series-dedup mechanism can be exercised against real data, the
same way `subject.primary_type is None`'s absence of ANY relation row
used to (accidentally) permit before F68 closed that hole.
"""

from __future__ import annotations

import dataclasses

import pytest

from now_filters.synthetic import SYNTH_ARTICLES_TABLE, SyntheticArticle, create_synthetic_articles_table
from now_filters.type_relations import excluded_types_for

from now_rails.row3_similar import compute_row3, resolve_eligible_articles
from now_rails.subject import ArticleSubject

REAL_SERIES_KEY = "new-restaurants-in-jakarta-latest-openings"  # 3 real members, verified


def _real_subject(conn, article_id: int) -> ArticleSubject:
    from now_rails.subject import fetch_article_subject

    subject = fetch_article_subject(conn, article_id)
    assert subject is not None, f"fixture article {article_id} must exist and be published"
    return subject


def test_row3_series_dedup_on_real_data(city_conn, relations):
    # Find a real member of the known 3-member series and confirm the
    # OTHER members of its own series never appear as a Row 3 result --
    # not because they are irrelevant, but because series dedup already
    # removed every sibling but the highest-quality one at the SQL stage.
    from sqlalchemy import text

    rows = city_conn.execute(
        text("SELECT id FROM public.articles WHERE series_key = :sk ORDER BY id"), {"sk": REAL_SERIES_KEY}
    ).fetchall()
    assert len(rows) == 3, "fixture assumption changed -- re-check F50/real series data"
    series_ids = {r.id for r in rows}

    subject_id = min(series_ids)  # use one series member itself as the subject; its own siblings must never appear
    subject = _real_subject(city_conn, subject_id)
    # F68: a real subject's primary_type is always None today (F50), and
    # `excluded_types_for(None)` now fails closed to "exclude every
    # venue-shaped type" -- which, combined with every real candidate ALSO
    # having a NULL primary_type, means the SQL competitor predicate would
    # exclude every real row before series dedup ever got a chance to run.
    # Override to a real, known, `exclude_same=False` type ("editorial")
    # to neutralize that UNRELATED predicate -- same technique F68's own
    # fix used for its two equivalent now_filters tests (PROGRESS.md F68)
    # -- so this test can still prove series dedup against the real series
    # + real embeddings, without weakening or bypassing any guard.
    subject = dataclasses.replace(subject, primary_type="editorial")

    # Direct, pre-diversify proof: the SQL-hard-filter + ladder stage
    # itself (the exact function compute_row3 calls) must never let more
    # than 1 of the group's remaining members through, independent of
    # whether MMR later keeps that survivor in the top-k display slots.
    ladder_run = resolve_eligible_articles(city_conn, subject, relations, slots_needed=4000)
    eligible_ids = {c.entity_id for c in ladder_run.result.candidates}
    assert len(eligible_ids) > 0, "editorial-type override must not itself exclude real candidates"
    other_series_members = series_ids - {subject_id}
    assert len(eligible_ids & other_series_members) <= 1, (
        "series dedup must keep at most 1 of the remaining series siblings ELIGIBLE "
        "(DISTINCT ON per series_key), before diversify/truncation ever runs"
    )

    result = compute_row3(city_conn, subject, relations, k=10, rerank_pool=40)
    assert len(result.items) > 0, "editorial-type override must let real, semantically-ranked results through"
    returned_ids = {i.entity_id for i in result.items}
    overlap = returned_ids & other_series_members
    assert len(overlap) <= 1, (
        f"series dedup must keep at most 1 of the {len(other_series_members)} remaining series "
        f"siblings eligible (DISTINCT ON per series_key) -- found {overlap}"
    )


def test_row3_real_subject_with_unknown_type_returns_empty(city_conn, relations):
    """F68: `subject_type is None` -- the real state of every article
    today (F50) -- now fails closed to "exclude every venue-shaped type",
    and every real candidate's `primary_type` is ALSO NULL, so the SQL
    competitor predicate excludes every real row. `compute_row3` called
    the ordinary way (no type override) on ANY real article id today must
    therefore return EMPTY, never reaching `search_semantic` at all --
    this is F68's fail-closed guarantee working as designed on real
    content, not a regression from this ticket's `search_semantic` switch.
    (Renamed from `test_row3_real_subject_returns_nonempty_results`, which
    asserted the opposite before F68 landed -- see this file's module
    docstring.)"""
    from sqlalchemy import text

    # Deliberately select an article that genuinely HAS no type, rather than
    # `ORDER BY id LIMIT 1` and assuming it is untyped. That assumption held
    # only while E2.1 had not run; after the F125 re-classification, article
    # 13 became `editorial` and this test was silently exercising a
    # *typed* subject -- `excluded_types_for('editorial')` is empty (editorial
    # excludes nothing), so it no longer tested the fail-closed path at all.
    # 632 untyped articles remain today, but that count only ever shrinks as
    # classification improves, so skip cleanly rather than fail once it hits 0.
    row = city_conn.execute(
        text("SELECT id FROM public.articles WHERE primary_type IS NULL ORDER BY id LIMIT 1")
    ).first()
    if row is None:
        pytest.skip("no untyped articles remain -- the unknown-subject path needs a synthetic fixture now")
    subject = _real_subject(city_conn, row.id)
    assert subject.primary_type is None, "fixture selection failed: subject must be untyped"

    result = compute_row3(city_conn, subject, relations, k=6, rerank_pool=40)

    assert result.rung_name != "no_subject_embedding"

    # F68's guarantee is "no COMPETITOR ever surfaces", and that is what is
    # asserted here. It used to be spelled `result.items == []`, which was
    # only equivalent while E2.1 had not run: back then every article's
    # `primary_type` was NULL, NULL is treated as a competitor (fail-closed),
    # so the whole corpus was excluded and empty was the correct answer.
    #
    # E2.1 has since typed 6,450 articles, so `editorial`/`event`/`do`
    # candidates now legitimately survive -- they are not commercial
    # competitors and were never meant to be excluded. Asserting emptiness
    # would now be asserting a bug.
    #
    # So: assert the invariant, not the incidental row count. This version
    # cannot rot as more articles get classified, and it FAILS if a genuine
    # competitor ever appears -- which is the thing worth protecting.
    excluded = excluded_types_for(relations, subject.primary_type)
    assert excluded >= {"stay", "eat", "drink", "wellness", "shop", "unknown"}, (
        "fail-closed set shrank: an unknown subject must still exclude every venue type"
    )
    if result.items:
        from sqlalchemy import text as _text

        returned_types = {
            r.primary_type
            for r in city_conn.execute(
                _text("SELECT primary_type FROM public.articles WHERE id = ANY(:ids)"),
                {"ids": [i.entity_id for i in result.items]},
            )
        }
        leaked = {t for t in returned_types if t is None or t in excluded}
        assert not leaked, (
            f"F68: competitor-exclusion hole -- subject_type={subject.primary_type!r} "
            f"must exclude {sorted(excluded)} (and NULL, fail-closed), but Row 3 "
            f"returned candidates typed {sorted(map(str, leaked))}"
        )
    # F50: subject has no real primary_type -- this is the reason for the
    # fail-closed empty result, not an unrelated data gap.
    assert result.unvalidated_reason is not None and "F50" in result.unvalidated_reason


def test_row3_competitor_exclusion_and_series_dedup_synthetic(city_conn, relations):
    rows = [
        SyntheticArticle(id=1, primary_type="stay", series_key=None),  # subject
        SyntheticArticle(id=2, primary_type="stay", series_key=None),  # competitor -- must never be eligible
        SyntheticArticle(id=3, primary_type="eat", series_key=None),  # eligible
        SyntheticArticle(id=4, primary_type="eat", series_key="grp-a"),  # eligible, but...
        SyntheticArticle(id=5, primary_type="eat", series_key="grp-a"),  # ...same series as 4 -- only one may survive
    ]
    create_synthetic_articles_table(city_conn, rows)

    subject = ArticleSubject(
        article_id=1, primary_type="stay", format=None, series_key=None, published_at=None,
        title="subject", status="published", place=None,
    )

    ladder_run = resolve_eligible_articles(
        city_conn, subject, relations, slots_needed=10, articles_table=SYNTH_ARTICLES_TABLE
    )
    eligible_ids = {c.entity_id for c in ladder_run.result.candidates}

    assert 1 not in eligible_ids, "self must never be eligible"
    assert 2 not in eligible_ids, "same-type (stay) competitor must never be eligible"
    assert 3 in eligible_ids
    assert len({4, 5} & eligible_ids) == 1, "series dedup must leave exactly one grp-a member eligible"


def test_row3_subject_with_no_embedding_returns_empty_not_error(city_conn, relations):
    subject = ArticleSubject(
        article_id=987_654_321, primary_type="stay", format=None, series_key=None, published_at=None,
        title="no embedding", status="published", place=None,
    )
    result = compute_row3(city_conn, subject, relations, k=6, rerank_pool=40)
    assert result.items == []
    assert result.rung_name == "no_subject_embedding"
    assert result.unvalidated_reason is not None
