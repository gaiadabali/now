"""Flatten `articles.body_blocks` (ARCHITECTURE.md Sec.5 schema) into one
plain-text string with a stable, reproducible mapping back to block order.

Deliberately re-derivable rather than cached: calling this twice on the
same `body_blocks` always yields byte-identical text, so `place_mentions.
offset` (an offset into THIS text) can be recomputed by any downstream
consumer (e.g. a future E4.3 span-inserter) without needing to store the
flattened text anywhere -- same "pure function of body_blocks" discipline
link-resolver's render.py uses.
"""

from __future__ import annotations

import re
from html import unescape

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"[ \t\f\v]+")
_NL_RE = re.compile(r"\n{3,}")

# Fields that carry the actual reader-facing prose for a block, in the
# order checked -- mirrors link-resolver's `_INLINE_HTML_FIELDS` plus the
# block-level fields body_blocks actually uses for prose (`text` isn't a
# real field on any shipped block type today, but is accepted here too in
# case a future block type adds one, matching link-resolver's own list).
_PROSE_FIELDS = ("html", "text")


def _strip_html(html: str) -> str:
    text = _TAG_RE.sub(" ", html or "")
    text = unescape(text)
    text = _WS_RE.sub(" ", text)
    return text.strip()


def _block_text(block: dict) -> str:
    btype = block.get("type")
    if btype == "heading" or btype == "paragraph" or btype == "quote":
        for field in _PROSE_FIELDS:
            if isinstance(block.get(field), str):
                return _strip_html(block[field])
        return ""
    if btype == "list":
        items = block.get("items") or []
        return "\n".join(_strip_html(i) for i in items if isinstance(i, str))
    if btype == "gallery":
        images = block.get("images") or []
        captions = [img.get("caption") for img in images if isinstance(img, dict) and img.get("caption")]
        return "\n".join(_strip_html(c) for c in captions)
    if btype == "image":
        caption = block.get("caption")
        return _strip_html(caption) if isinstance(caption, str) else ""
    if btype == "columns":
        cols = block.get("columns") or []
        parts = []
        for col in cols:
            if isinstance(col, list):
                parts.extend(_block_text(b) for b in col if isinstance(b, dict))
        return "\n".join(p for p in parts if p)
    if btype == "raw_html":
        html = block.get("html")
        return _strip_html(html) if isinstance(html, str) else ""
    # separator, embed and anything unrecognised carry no venue-bearing prose.
    return ""


def flatten(body_blocks: list[dict] | None) -> str:
    """Return the plain-text concatenation of every block's prose, each
    block joined by a blank line so offsets never straddle a block
    boundary ambiguously."""
    if not body_blocks:
        return ""
    parts = [t for t in (_block_text(b) for b in body_blocks if isinstance(b, dict)) if t]
    text = "\n\n".join(parts)
    return _NL_RE.sub("\n\n", text)
