"""Content-loss measurement: visible-text characters in (raw `content_html`)
vs. out (the block array), per article.

"Visible text" = what a reader would actually see rendered — tags and
attributes stripped, entities decoded, whitespace collapsed. Image `alt`
text is deliberately excluded from both sides (it's an attribute, not
rendered text, unless the image fails to load) so it doesn't manufacture
a false sense of preservation; `figcaption`/shortcode caption text *is*
included on both sides since captions do render.
"""

from __future__ import annotations

import re
from typing import Any

import lxml.html

from now_content_clean.html_blocks import (
    _NON_VISIBLE_TAGS,
    apply_render_boundaries,
    strip_tags_text,
)

_WS_RE = re.compile(r"\s+")


def _normalize(text: str) -> str:
    return _WS_RE.sub(" ", text).strip()


def _text_excluding_non_visible(fragment_html: str) -> str:
    """Like `strip_tags_text`, but first removes <script>/<style>/<svg>
    subtrees entirely — lxml's `text_content()` otherwise happily
    includes a `<script>` tag's JS source as "text", which would make the
    loss metric flag deliberately-dropped tracking scripts as content
    loss when they're not content at all (a reader's browser never
    renders that text either)."""
    wrapper = lxml.html.fragment_fromstring(fragment_html, create_parent="div")
    for tag in _NON_VISIBLE_TAGS:
        for el in wrapper.findall(f".//{tag}"):
            # lxml's `remove()` discards the element's *tail* text too —
            # correct for the element's own (non-visible) content, but
            # WordPress content routinely has real bare-text paragraphs
            # sitting as an unwrapped `<script>`'s tail (no enclosing
            # tag). Re-home the tail before removing, exactly like the
            # main block walker's `add_text(child.tail)` already does,
            # so this metric doesn't manufacture a false "loss".
            tail = el.tail
            parent = el.getparent()
            if parent is None:
                continue
            if tail:
                prev = el.getprevious()
                if prev is not None:
                    prev.tail = (prev.tail or "") + tail
                else:
                    parent.text = (parent.text or "") + tail
            parent.remove(el)
    # Same boundary rules as the output side, or the metric compares a welded
    # "thecolonial" against a correctly-spaced "the colonial" and reports a
    # phantom delta. Both sides must flatten markup identically.
    apply_render_boundaries(wrapper)
    return wrapper.text_content()


def visible_text_in(content_html: str) -> str:
    """Visible text of the raw source, with WP shortcode/comment markers
    removed first so they don't get miscounted as "lost" content on the
    output side (they're markup, not prose)."""
    from now_content_clean.gutenberg import strip_wp_comments

    cleaned = strip_wp_comments(content_html)
    cleaned = re.sub(r"\[caption[^\]]*\]|\[/caption\]|\[gallery[^\]]*\]", "", cleaned, flags=re.IGNORECASE)
    return _normalize(_text_excluding_non_visible(cleaned)) if cleaned.strip() else ""


def _block_visible_text(block: dict[str, Any]) -> str:
    t = block.get("type")
    if t == "paragraph" or t == "quote" or t == "raw_html":
        parts = [strip_tags_text(block.get("html", ""))]
        if t == "quote" and block.get("cite"):
            parts.append(block["cite"])
        return " ".join(p for p in parts if p)
    if t == "heading":
        return block.get("text", "")
    if t == "list":
        return " ".join(strip_tags_text(i) for i in block.get("items", []))
    if t == "image":
        return block.get("caption") or ""
    if t == "gallery":
        parts = [img.get("caption") or "" for img in block.get("images", [])]
        if block.get("caption"):
            parts.append(block["caption"])
        return " ".join(p for p in parts if p)
    if t == "columns":
        return " ".join(_block_visible_text(b) for col in block.get("columns", []) for b in col)
    if t in ("embed", "separator"):
        return ""
    return ""


def visible_text_out(blocks: list[dict[str, Any]]) -> str:
    return _normalize(" ".join(_block_visible_text(b) for b in blocks if _block_visible_text(b)))


def word_delta(text_in: str, text_out: str) -> dict:
    """Word-multiset comparison — catches the defect class a character count
    is structurally blind to.

    Welding two words together ("the<br>colonial" -> "thecolonial") removes a
    tag and joins two tokens. The character count is UNCHANGED, so `loss_pct`
    stays 0.000% while the text is corrupted. That is exactly how the original
    `<br>` bug survived a "median 0.000% loss" verification.

    A weld shows up here as 2 words lost and 1 gained.
    """
    from collections import Counter

    win = Counter(text_in.split())
    wout = Counter(text_out.split())
    lost = win - wout
    gained = wout - win
    return {
        "words_lost": sum(lost.values()),
        "words_gained": sum(gained.values()),
        "sample_lost": sorted(lost)[:5],
        "sample_gained": sorted(gained)[:5],
    }


def content_loss(content_html: str, blocks: list[dict[str, Any]]) -> dict:
    text_in = visible_text_in(content_html)
    text_out = visible_text_out(blocks)
    chars_in, chars_out = len(text_in), len(text_out)
    delta = chars_in - chars_out
    pct = (delta / chars_in * 100) if chars_in else 0.0
    return {
        "chars_in": chars_in,
        "chars_out": chars_out,
        "delta": delta,
        "loss_pct": round(pct, 3),
        # Never report loss_pct without this alongside it — a character count
        # alone cannot see word welding, and reporting it alone is what made
        # the original bug invisible.
        "word_delta": word_delta(text_in, text_out),
    }
