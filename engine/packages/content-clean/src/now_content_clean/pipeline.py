"""Entry points: `clean_html` (pure HTML -> blocks) and `clean_article`
(the full E1.1-contract article dict -> CleanResult with links, uploads,
and a content-loss report)."""

from __future__ import annotations

from typing import Any

from now_content_clean import gutenberg, metrics
from now_content_clean.html_blocks import blocks_from_fragment
from now_content_clean.links import extract_links, extract_uploads
from now_content_clean.models import CleanResult
from now_content_clean.shortcodes import preprocess_shortcodes


def clean_html(content_html: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Pure function: raw `content_html` -> (blocks, stats). Deterministic
    and side-effect free, so running it twice on the same input (or on a
    previous run's own output, which is just HTML) is always idempotent."""
    stats: dict[str, Any] = {}
    if not content_html:
        return [], stats

    gutenberg.scan_blocks(content_html, stats)
    stage1 = preprocess_shortcodes(content_html, stats)
    stage2 = gutenberg.strip_wp_comments(stage1)
    blocks = blocks_from_fragment(stage2, stats)
    return blocks, stats


def clean_article(article: dict[str, Any]) -> CleanResult:
    """`article` follows the frozen E1.1 contract
    (`jakarta/content/extracted/articles.jsonl`): must have `wp_id` and
    `content_html`."""
    content_html = article.get("content_html") or ""
    blocks, stats = clean_html(content_html)

    links = extract_links(content_html)
    uploads = extract_uploads(content_html)
    stats["links_extracted"] = len(links)
    stats["uploads_extracted"] = len(uploads)
    stats["content_loss"] = metrics.content_loss(content_html, blocks)

    return CleanResult(
        wp_id=article.get("wp_id"),
        blocks=blocks,
        links=links,
        uploads=uploads,
        stats=stats,
    )
