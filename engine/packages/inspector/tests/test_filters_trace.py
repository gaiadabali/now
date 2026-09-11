from now_inspector.filters_trace import (
    build_trace,
    survived,
    trace_competitor,
    trace_quality_floor,
    trace_self,
    trace_series_dedup,
    trace_status,
)
from now_inspector.models import ArticleRow, QualityBreakdown


def _article(**kw) -> ArticleRow:
    base = dict(
        id=1,
        title="t",
        dek=None,
        legacy_wp_id=None,
        legacy_permalink=None,
        primary_type=None,
        format=None,
        series_key=None,
        status="published",
        published_at=None,
    )
    base.update(kw)
    return ArticleRow(**base)


def test_status_removes_unpublished():
    e = trace_status(_article(status="draft"))
    assert e.removed is True


def test_status_none_article_is_removed():
    e = trace_status(None)
    assert e.removed is True


def test_self_only_applies_in_article_id_mode():
    assert trace_self(5, None) is None
    assert trace_self(5, 5).removed is True
    assert trace_self(5, 6).removed is False


def test_competitor_null_primary_type_is_not_classified_yet():
    e = trace_competitor(_article(primary_type=None), _article(id=2, primary_type=None))
    assert e.removed is False
    assert e.data_status == "not classified yet"


def test_competitor_same_l1_removed():
    e = trace_competitor(_article(primary_type="stay/hotel"), _article(id=2, primary_type="stay/villa"))
    assert e.removed is True
    assert e.data_status == "available"


def test_competitor_different_l1_kept():
    e = trace_competitor(_article(primary_type="eat/cafe"), _article(id=2, primary_type="stay/hotel"))
    assert e.removed is False


def test_series_dedup_keeps_current_removes_others():
    q_current = QualityBreakdown(entity_id="1", score=0.5, components={"series": {"is_current": True}}, found=True)
    q_old = QualityBreakdown(entity_id="2", score=0.5, components={"series": {"is_current": False}}, found=True)
    article = _article(series_key="x")
    assert trace_series_dedup(article, q_current).removed is False
    assert trace_series_dedup(article, q_old).removed is True


def test_series_dedup_no_series_key_not_applicable():
    e = trace_series_dedup(_article(series_key=None), None)
    assert e.data_status == "not applicable"
    assert e.removed is False


def test_quality_floor_below_removed():
    q = QualityBreakdown(entity_id="1", score=0.1, components={"quality_floor_reference": 0.35}, found=True)
    assert trace_quality_floor(q).removed is True


def test_quality_floor_above_kept():
    q = QualityBreakdown(entity_id="1", score=0.9, components={"quality_floor_reference": 0.35}, found=True)
    assert trace_quality_floor(q).removed is False


def test_quality_floor_missing_data_is_not_classified_yet():
    e = trace_quality_floor(None)
    assert e.data_status == "not classified yet"
    assert e.removed is False


def test_build_trace_and_survived_aggregate():
    q = QualityBreakdown(entity_id="1", score=0.9, components={"quality_floor_reference": 0.35}, found=True)
    article = _article(status="published")
    trace = build_trace(article=article, entity_id="1", quality=q, seed_article=None, seed_article_id=None)
    ok, reason = survived(trace)
    assert ok is True

    trace_bad = build_trace(
        article=_article(status="draft"), entity_id="1", quality=q, seed_article=None, seed_article_id=None
    )
    ok2, reason2 = survived(trace_bad)
    assert ok2 is False
    assert "status" in reason2
