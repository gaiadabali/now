"""Outbound-link and inline-upload extraction — feeds E1.5 (partner-roster
clustering) and E1.3 (media URL rewrite)."""

from __future__ import annotations

from now_content_clean.links import extract_links, extract_uploads
from now_content_clean.pipeline import clean_article


def test_extract_links_offset_and_anchor_text():
    html = '<p>Check out <a href="https://example.com/page">this great site</a> today.</p>'
    links = extract_links(html)
    assert len(links) == 1
    link = links[0]
    assert link.href == "https://example.com/page"
    assert link.text == "this great site"
    assert html[link.offset : link.offset + 2] == "<a"


def test_extract_links_preserves_rel_attribute_faithfully():
    html = '<a href="https://partner.example.com" rel="nofollow">Partner</a>'
    links = extract_links(html)
    assert links[0].rel == "nofollow"

    html_no_rel = '<a href="https://partner.example.com">Partner</a>'
    assert extract_links(html_no_rel)[0].rel is None


def test_extract_links_marks_upload_links():
    html = '<a href="http://nowjakarta.co.id/wp-content/uploads/2019/img.jpg">Full size</a>'
    link = extract_links(html)[0]
    assert link.is_upload is True


def test_extract_links_with_inline_formatting_inside_anchor():
    html = '<p><strong><a href="https://x.com/a">Bold Link Text</a></strong></p>'
    links = extract_links(html)
    assert links[0].text == "Bold Link Text"


def test_extract_multiple_links_with_distinct_offsets():
    html = '<p><a href="https://a.com">A</a> and <a href="https://b.com">B</a></p>'
    links = extract_links(html)
    assert len(links) == 2
    assert links[0].offset < links[1].offset
    assert links[0].href == "https://a.com"
    assert links[1].href == "https://b.com"


def test_extract_uploads_from_img_src():
    html = '<img src="https://x.com/wp-content/uploads/2020/05/photo.jpg" alt="" />'
    uploads = extract_uploads(html)
    assert len(uploads) == 1
    assert uploads[0].url == "https://x.com/wp-content/uploads/2020/05/photo.jpg"
    assert uploads[0].context == "img_src"


def test_extract_uploads_from_href():
    html = '<a href="http://nowjakarta.co.id/wp-content/uploads/2016/12/x.jpg">link</a>'
    uploads = extract_uploads(html)
    assert uploads[0].context == "a_href"


def test_links_extracted_survive_into_clean_article_result(articles):
    linky = [a for a in articles if "<a " in a["content_html"] or "<a\t" in a["content_html"] or "<a\n" in a["content_html"]]
    found_any = False
    for article in articles:
        result = clean_article(article)
        if result.links:
            found_any = True
            for link in result.links:
                assert article["content_html"][link.offset : link.offset + 2] == "<a"
    assert found_any, "fixture sample must contain at least one article with outbound links"


def test_uploads_extracted_for_articles_with_inline_uploads(articles):
    upload_articles = [a for a in articles if "wp-content/uploads" in a["content_html"]]
    assert len(upload_articles) >= 10, "fixture sample must cover the 45%-of-articles inline-uploads case"
    for article in upload_articles:
        result = clean_article(article)
        assert len(result.uploads) > 0
