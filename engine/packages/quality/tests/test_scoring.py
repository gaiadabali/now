from now_quality.scoring import (
    QUALITY_FLOOR,
    STUB_CHAR_THRESHOLD,
    STUB_SCORE_CAP,
    Weights,
    compute_quality,
)
from now_quality.textextract import article_text_stats


def _stats_for_chars(chars: int, **extra_blocks_kwargs) -> "object":
    text = "x" * chars
    return article_text_stats([{"type": "paragraph", "html": text}])


def test_stub_under_500_chars_falls_below_the_floor_even_with_everything_else_maxed():
    stats = _stats_for_chars(50)
    result = compute_quality(
        stats=stats,
        author_id=1,
        hero_media_id=1,
        has_focuskw=True,
        has_metadesc=True,
        has_primary_category=True,
    )
    assert result.is_stub is True
    assert result.score <= STUB_SCORE_CAP
    assert result.score < QUALITY_FLOOR


def test_well_developed_article_scores_above_the_floor():
    blocks = [
        {"type": "heading", "level": 2, "text": "A"},
        {"type": "paragraph", "html": "word " * 800},
        {"type": "heading", "level": 2, "text": "B"},
        {"type": "list", "items": ["one", "two", "three"]},
        {"type": "image", "media_ref": "a.jpg"},
        {"type": "image", "media_ref": "b.jpg"},
    ]
    stats = article_text_stats(blocks)
    result = compute_quality(
        stats=stats,
        author_id=7,
        hero_media_id=99,
        has_focuskw=True,
        has_metadesc=True,
        has_primary_category=True,
    )
    assert result.is_stub is False
    assert result.score > QUALITY_FLOOR


def test_empty_article_is_a_stub():
    stats = article_text_stats([])
    result = compute_quality(
        stats=stats, author_id=None, hero_media_id=None,
        has_focuskw=False, has_metadesc=False, has_primary_category=False,
    )
    assert result.is_stub is True
    assert result.score <= STUB_SCORE_CAP


def test_weights_must_sum_to_one():
    import pytest

    with pytest.raises(ValueError):
        Weights(length=0.5, structure=0.5, media=0.5, author=0.1, yoast=0.1)


def test_components_are_json_serializable():
    import json

    stats = _stats_for_chars(1000)
    result = compute_quality(
        stats=stats, author_id=1, hero_media_id=1,
        has_focuskw=False, has_metadesc=True, has_primary_category=False,
    )
    json.dumps(result.components)  # must not raise
    assert result.components["length"]["chars"] == 1000
    assert 0.0 <= result.score <= 1.0


def test_stub_char_threshold_matches_ticket():
    assert STUB_CHAR_THRESHOLD == 500
