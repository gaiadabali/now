from now_quality.textextract import article_text_stats, strip_html


def test_strip_html_decodes_entities_and_collapses_whitespace():
    assert strip_html("<p>Hello&nbsp;<b>world</b></p>\n\n  more") == "Hello world more"


def test_empty_body_blocks_is_all_zero():
    stats = article_text_stats([])
    assert stats.chars == 0
    assert stats.media_count == 0
    assert stats.heading_count == 0


def test_none_body_blocks_does_not_raise():
    stats = article_text_stats(None)
    assert stats.chars == 0


def test_counts_headings_media_and_chars():
    blocks = [
        {"type": "heading", "level": 2, "text": "Intro"},
        {"type": "paragraph", "html": "<p>Some real body copy here.</p>"},
        {"type": "image", "media_ref": "x.jpg", "caption": "A photo"},
        {"type": "gallery", "images": [{"caption": "one"}, {"caption": "two"}]},
        {"type": "list", "ordered": False, "items": ["a", "b", "c"]},
        {"type": "quote", "html": "<p>Wise words</p>", "cite": "Someone"},
        {"type": "embed", "provider": "youtube", "url": "https://youtu.be/x"},
        {"type": "separator"},
    ]
    stats = article_text_stats(blocks)
    assert stats.heading_count == 1
    assert stats.media_count == 1 + 2 + 1  # image + gallery(2) + embed
    assert stats.distinct_rich_types == {"heading", "list", "quote", "gallery", "embed"}.__len__()
    assert stats.chars > 0


def test_columns_recurse_into_nested_blocks():
    blocks = [
        {
            "type": "columns",
            "columns": [
                [{"type": "paragraph", "html": "left column text"}],
                [{"type": "paragraph", "html": "right column text"}],
            ],
        }
    ]
    stats = article_text_stats(blocks)
    assert stats.chars == len("left column text right column text")
