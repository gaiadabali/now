"""General block-schema conformance over classic (non-Gutenberg) content
and the "don't silently drop, count it" contract."""

from __future__ import annotations

from now_content_clean.pipeline import clean_article, clean_html

ALLOWED_TYPES = {
    "heading", "paragraph", "image", "gallery", "list", "quote", "embed",
    "raw_html", "separator", "columns",
}


def test_all_fixture_blocks_use_a_recognised_type(articles):
    for article in articles:
        result = clean_article(article)
        for block in result.blocks:
            assert block["type"] in ALLOWED_TYPES, f"wp_id={article['wp_id']} emitted unknown block type {block['type']}"


def test_classic_paragraph():
    html = "<p>Just a simple paragraph with <strong>bold</strong> text.</p>"
    blocks, _ = clean_html(html)
    assert blocks == [{"type": "paragraph", "html": "Just a simple paragraph with <strong>bold</strong> text."}]


def test_classic_heading_levels():
    for level in range(1, 7):
        blocks, _ = clean_html(f"<h{level}>Title {level}</h{level}>")
        assert blocks[0] == {"type": "heading", "level": level, "text": f"Title {level}", "html": f"Title {level}"}


def test_classic_image_only_paragraph_becomes_image_block():
    html = '<p class="image-center"><a href="https://x.com/full.jpg"><img src="https://x.com/thumb.jpg" alt="A photo"/></a></p>'
    blocks, _ = clean_html(html)
    assert blocks == [
        {"type": "image", "media_ref": "https://x.com/thumb.jpg", "alt": "A photo", "caption": None, "href": "https://x.com/full.jpg"}
    ]


def test_classic_unordered_list():
    html = "<ul><li>One</li><li>Two with <em>emphasis</em></li></ul>"
    blocks, _ = clean_html(html)
    assert blocks == [{"type": "list", "ordered": False, "items": ["One", "Two with <em>emphasis</em>"]}]


def test_classic_blockquote_without_cite():
    html = "<blockquote><h3>A pull quote as a heading</h3></blockquote>"
    blocks, _ = clean_html(html)
    assert blocks[0]["type"] == "quote"
    assert blocks[0]["cite"] is None


def test_bare_iframe_becomes_embed():
    html = '<iframe src="https://www.youtube.com/embed/abc123"></iframe>'
    blocks, _ = clean_html(html)
    assert blocks == [{"type": "embed", "provider": "youtube", "url": "https://www.youtube.com/embed/abc123"}]


def test_bare_google_maps_iframe_classified():
    html = '<iframe src="https://www.google.com/maps/embed?pb=abc"></iframe>'
    blocks, _ = clean_html(html)
    assert blocks[0]["provider"] == "google_maps"


def test_hr_becomes_separator():
    blocks, _ = clean_html("<hr />")
    assert blocks == [{"type": "separator"}]


def test_table_is_preserved_as_raw_html_and_counted():
    html = "<table><tr><td>cell</td></tr></table>"
    blocks, stats = clean_html(html)
    assert blocks[0]["type"] == "raw_html"
    assert "cell" in blocks[0]["html"]
    assert blocks[0]["reason"] == "unhandled_tag:table"
    assert stats["unhandled_tags"]["table"] == 1


def test_script_is_dropped_and_counted_not_left_in_output():
    html = "<p>Visible text.</p><script>var x = 'not content';</script>"
    blocks, stats = clean_html(html)
    assert len(blocks) == 1
    assert blocks[0]["type"] == "paragraph"
    assert "not content" not in str(blocks)
    assert stats["dropped_non_visible"] == 1


def test_empty_paragraph_dropped_and_counted():
    blocks, stats = clean_html("<p>&nbsp;</p>")
    assert blocks == []
    assert stats["dropped_empty"] == 1


def test_bare_text_not_wrapped_in_any_tag_is_preserved_as_paragraph():
    html = "<h2>Heading</h2>\nSome bare text with no wrapping tag at all."
    blocks, _ = clean_html(html)
    assert blocks[1] == {"type": "paragraph", "html": "Some bare text with no wrapping tag at all."}


def test_columns_block_preserves_both_columns_content():
    html = (
        '<div class="wp-block-columns">'
        '<div class="wp-block-column"><p>Left</p></div>'
        '<div class="wp-block-column"><p>Right</p></div>'
        "</div>"
    )
    blocks, _ = clean_html(html)
    assert blocks[0]["type"] == "columns"
    assert blocks[0]["columns"][0] == [{"type": "paragraph", "html": "Left"}]
    assert blocks[0]["columns"][1] == [{"type": "paragraph", "html": "Right"}]


def test_document_noise_html_meta_tags_stripped_not_lost():
    html = "<html><p>Body text survives.</p><meta charset=\"utf-8\" /></html>"
    blocks, _ = clean_html(html)
    text = " ".join(b.get("html", b.get("text", "")) for b in blocks)
    assert "Body text survives." in text


def test_empty_content_html_returns_empty_blocks():
    blocks, stats = clean_html("")
    assert blocks == []
    assert stats == {}
