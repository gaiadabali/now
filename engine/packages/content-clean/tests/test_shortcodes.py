"""[caption] (17 archive-wide) and [gallery] shortcode handling."""

from __future__ import annotations

from now_content_clean.pipeline import clean_article, clean_html


def test_well_formed_caption_shortcode_becomes_image_with_caption():
    html = (
        '[caption id="attachment_123" align="aligncenter" width="700"]'
        '<img class="wp-image-123" src="https://x.com/a.jpg" alt=""/> A nice caption'
        "[/caption]"
    )
    blocks, stats = clean_html(html)
    assert blocks == [
        {"type": "image", "media_ref": "https://x.com/a.jpg", "alt": "", "caption": "A nice caption", "href": None}
    ]
    assert stats["shortcode_caption"] == 1


def test_caption_shortcode_wrapping_a_linked_image():
    html = (
        '[caption id="attachment_1" align="aligncenter" width="1024"]'
        '<a href="https://x.com/full.jpg"><img class="wp-image-1" src="https://x.com/thumb.jpg" alt=""/></a>'
        " credit line[/caption]"
    )
    blocks, _ = clean_html(html)
    assert blocks[0]["type"] == "image"
    assert blocks[0]["href"] == "https://x.com/full.jpg"
    assert blocks[0]["caption"] == "credit line"


def test_malformed_caption_shortcode_does_not_lose_surrounding_content(articles_by_id):
    """wp_id 5022 is a real, malformed instance: the opening
    `[caption ...]` is HTML-entity-escaped and there's no matching
    `[/caption]` nearby (a broken historical copy/paste). Content-clean
    must not invent structure it can't verify — but it also must not
    drop a single visible character of the surrounding, otherwise-intact
    HTML."""
    article = articles_by_id[5022]
    result = clean_article(article)
    loss = result.stats["content_loss"]
    assert loss["chars_out"] == loss["chars_in"]
    assert stray_marker_absent(result.blocks)


def stray_marker_absent(blocks) -> bool:
    import json

    return "[caption" not in json.dumps(blocks) and "[/caption]" not in json.dumps(blocks)


def test_gallery_shortcode_with_ids_only():
    html = '[gallery ids="1,2,3" columns="3"]'
    blocks, stats = clean_html(html)
    assert blocks == [{"type": "gallery", "images": [], "ids": ["1", "2", "3"]}]
    assert stats["shortcode_gallery"] == 1


def test_all_17_caption_shortcode_fixtures_run_clean(articles):
    caption_articles = [a for a in articles if "[caption" in a["content_html"]]
    assert len(caption_articles) == 17, "the archive has exactly 17 [caption] instances"
    for article in caption_articles:
        result = clean_article(article)
        assert isinstance(result.blocks, list)
        loss = result.stats["content_loss"]
        assert loss["chars_out"] == loss["chars_in"], f"wp_id={article['wp_id']} lost content around a [caption] shortcode"
