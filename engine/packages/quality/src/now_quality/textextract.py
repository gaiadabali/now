"""Extracts plain-text statistics from `public.articles.body_blocks`
(ARCHITECTURE.md Sec.5's shipped block schema) for the length/media/
structure quality components.

Not a rendering pipeline -- just enough fidelity to count visible
characters and structural signals consistently across the corpus. Uses a
regex tag-stripper rather than lxml: this package doesn't otherwise need an
HTML parser, and a stripped-down count is exactly what the "wall of text
vs structured" signal needs -- perfect fidelity isn't.
"""

from __future__ import annotations

import html
import re
from dataclasses import dataclass, field

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")

# Block types that carry visible body copy vs. structural/media-only types.
# Matches the shipped schema in ARCHITECTURE.md Sec.5: heading, paragraph,
# image, gallery, list, quote, embed, separator, columns, raw_html.
_RICH_STRUCTURE_TYPES = {"heading", "list", "quote", "gallery", "embed", "columns"}


def strip_html(fragment: str | None) -> str:
    """Visible text of one HTML fragment: tags dropped, entities decoded,
    whitespace collapsed."""
    if not fragment:
        return ""
    text = _TAG_RE.sub(" ", fragment)
    text = html.unescape(text)
    return _WS_RE.sub(" ", text).strip()


def _block_text(block: dict) -> str:
    btype = block.get("type")
    if btype == "heading":
        return block.get("text") or strip_html(block.get("html"))
    if btype == "paragraph":
        return strip_html(block.get("html"))
    if btype == "quote":
        return strip_html(block.get("html")) + " " + (block.get("cite") or "")
    if btype == "list":
        return " ".join(str(item) for item in (block.get("items") or []))
    if btype == "image":
        return strip_html(block.get("caption"))
    if btype == "gallery":
        return " ".join(strip_html(img.get("caption")) for img in (block.get("images") or []))
    if btype == "raw_html":
        return strip_html(block.get("html"))
    if btype == "columns":
        return " ".join(_block_text(b) for col in (block.get("columns") or []) for b in col)
    # embed, separator: no visible body copy
    return ""


@dataclass
class ArticleTextStats:
    chars: int = 0
    heading_count: int = 0
    media_count: int = 0  # images (incl. gallery members) + embeds
    distinct_rich_types: int = 0
    block_count: int = 0

    # kept for the report / debugging, not scored directly
    type_counts: dict = field(default_factory=dict)


def article_text_stats(body_blocks: list | None) -> ArticleTextStats:
    """Walks `body_blocks` once and returns the counts the scoring module
    needs. Empty/`None` input (the sub-500-char stub case, or a genuinely
    empty `[]`) returns an all-zero stats object -- never raises."""
    stats = ArticleTextStats()
    if not body_blocks:
        return stats

    seen_rich_types: set[str] = set()
    text_parts: list[str] = []

    def walk(blocks: list) -> None:
        for block in blocks:
            if not isinstance(block, dict):
                continue
            btype = block.get("type")
            stats.block_count += 1
            stats.type_counts[btype] = stats.type_counts.get(btype, 0) + 1

            if btype == "heading":
                stats.heading_count += 1
            if btype in _RICH_STRUCTURE_TYPES:
                seen_rich_types.add(btype)
            if btype == "image":
                stats.media_count += 1
            elif btype == "gallery":
                stats.media_count += len(block.get("images") or [])
            elif btype == "embed":
                stats.media_count += 1

            if btype == "columns":
                for col in block.get("columns") or []:
                    walk(col)
            else:
                text_parts.append(_block_text(block))

    walk(body_blocks)
    stats.distinct_rich_types = len(seen_rich_types)
    stats.chars = len(_WS_RE.sub(" ", " ".join(p for p in text_parts if p)).strip())
    return stats
