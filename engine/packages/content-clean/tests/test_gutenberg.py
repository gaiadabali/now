"""Gutenberg-specific acceptance criterion: block comments are parsed as
structure and never survive into the output as literal text."""

from __future__ import annotations

import json

from now_content_clean.pipeline import clean_article, clean_html


def _has_literal_wp_comment(obj) -> bool:
    s = json.dumps(obj)
    return "<!-- wp:" in s or "<!--wp:" in s or "/wp:" in s


def test_no_gutenberg_articles_leak_literal_comment_text(articles):
    gutenberg_articles = [a for a in articles if "<!-- wp:" in a["content_html"]]
    assert len(gutenberg_articles) >= 20
    for article in gutenberg_articles:
        result = clean_article(article)
        assert not _has_literal_wp_comment(result.blocks), (
            f"wp_id={article['wp_id']} leaked a literal wp: comment into blocks"
        )


def test_heading_level_recovered_from_gutenberg_block():
    html = (
        '<!-- wp:heading {"level":3} -->\n'
        '<h3 class="wp-block-heading">A subheading</h3>\n'
        "<!-- /wp:heading -->"
    )
    blocks, _ = clean_html(html)
    assert blocks == [{"type": "heading", "level": 3, "text": "A subheading", "html": "A subheading"}]


def test_ordered_list_recovered_from_gutenberg_block():
    html = (
        "<!-- wp:list {\"ordered\":true} -->\n"
        "<ol><!-- wp:list-item -->\n<li>First</li>\n<!-- /wp:list-item -->\n\n"
        "<!-- wp:list-item -->\n<li>Second</li>\n<!-- /wp:list-item --></ol>\n"
        "<!-- /wp:list -->"
    )
    blocks, _ = clean_html(html)
    assert blocks == [{"type": "list", "ordered": True, "items": ["First", "Second"]}]


def test_gallery_block_collects_each_image_and_caption():
    html = (
        '<!-- wp:gallery {"linkTo":"none"} -->\n'
        '<figure class="wp-block-gallery has-nested-images columns-default is-cropped">'
        '<!-- wp:image {"id":1} -->\n'
        '<figure class="wp-block-image size-large"><img src="https://x/a.jpg" alt=""/>'
        '<figcaption class="wp-element-caption">Caption A</figcaption></figure>\n'
        "<!-- /wp:image -->\n\n"
        '<!-- wp:image {"id":2} -->\n'
        '<figure class="wp-block-image size-large"><img src="https://x/b.jpg" alt=""/>'
        '<figcaption class="wp-element-caption">Caption B</figcaption></figure>\n'
        "<!-- /wp:image --></figure>\n"
        "<!-- /wp:gallery -->"
    )
    blocks, _ = clean_html(html)
    assert len(blocks) == 1
    assert blocks[0]["type"] == "gallery"
    captions = [img["caption"] for img in blocks[0]["images"]]
    assert captions == ["Caption A", "Caption B"], "each gallery image must keep its own caption, not just the first"


def test_embed_block_url_and_provider():
    html = (
        '<!-- wp:embed {"url":"https://www.youtube.com/watch?v=abc123","type":"video",'
        '"providerNameSlug":"youtube"} -->\n'
        '<figure class="wp-block-embed is-type-video is-provider-youtube">'
        '<div class="wp-block-embed__wrapper">\nhttps://www.youtube.com/watch?v=abc123\n</div></figure>\n'
        "<!-- /wp:embed -->"
    )
    blocks, _ = clean_html(html)
    assert blocks == [{"type": "embed", "provider": "youtube", "url": "https://www.youtube.com/watch?v=abc123"}]


def test_quote_block_extracts_cite():
    html = (
        "<!-- wp:quote -->\n"
        '<blockquote class="wp-block-quote"><!-- wp:paragraph -->\n'
        "<p>A memorable line.</p>\n"
        "<!-- /wp:paragraph --><cite>Someone Famous</cite></blockquote>\n"
        "<!-- /wp:quote -->"
    )
    blocks, _ = clean_html(html)
    assert len(blocks) == 1
    assert blocks[0]["type"] == "quote"
    assert blocks[0]["cite"] == "Someone Famous"
    assert "A memorable line." in blocks[0]["html"]


def test_separator_and_spacer():
    html = (
        "<!-- wp:separator -->\n<hr/>\n<!-- /wp:separator -->\n"
        '<!-- wp:spacer {"height":"10px"} -->\n'
        '<div style="height:10px" class="wp-block-spacer"></div>\n'
        "<!-- /wp:spacer -->"
    )
    blocks, stats = clean_html(html)
    assert blocks == [{"type": "separator"}]  # spacer carries zero text, dropped
    assert stats["dropped_decorative"] == 1


def test_gutenberg_block_types_are_counted_for_the_report():
    html = (
        "<!-- wp:paragraph -->\n<p>Hi</p>\n<!-- /wp:paragraph -->\n"
        "<!-- wp:paragraph -->\n<p>There</p>\n<!-- /wp:paragraph -->"
    )
    _, stats = clean_html(html)
    assert stats["gutenberg_block_types"]["paragraph"] == 2
