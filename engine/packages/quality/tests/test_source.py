import json

from now_quality.source import load_source_meta


def test_load_source_meta_reads_views_and_yoast(tmp_path):
    p = tmp_path / "articles.jsonl"
    rows = [
        {"wp_id": 1, "meta": {"wpb_post_views_count": "1234", "_yoast_wpseo_focuskw": "jakarta food"}},
        {"wp_id": 2, "meta": {"wpb_post_views_count": "500"}},
        {"wp_id": 3, "meta": {}},
    ]
    p.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")

    result = load_source_meta(p)
    assert result[1].views == 1234
    assert result[1].has_focuskw is True
    assert result[2].views == 500
    assert result[2].has_focuskw is False
    assert result[3].views is None


def test_load_source_meta_skips_blank_lines(tmp_path):
    p = tmp_path / "articles.jsonl"
    p.write_text('{"wp_id": 1, "meta": {}}\n\n', encoding="utf-8")
    result = load_source_meta(p)
    assert 1 in result
