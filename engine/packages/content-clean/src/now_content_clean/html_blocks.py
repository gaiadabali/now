"""Classic-HTML -> blocks.

This is the single engine used for:

  - plain classic-editor content (86% of the archive, `<p>` tags),
  - Gutenberg block content, *after* the `<!-- wp:... -->` / `<!-- /wp:...
    -->` comment markers are stripped (see `gutenberg.strip_wp_comments`).
    A Gutenberg block is, on disk, a structural comment wrapped around
    otherwise complete, self-describing HTML (`<h2>` already carries its
    level, `<ol>`/`<ul>` already carries orderedness, `wp-block-gallery`
    already nests one `<figure>` per photo, ...). Stripping the comments
    and reusing the *same* generic HTML walker satisfies "parsed as
    structure, never left as literal text" without needing a second,
    parallel, hand-rolled block-tree parser that duplicates every rule
    here and would only diverge from it over time. The one piece of
    signal that lives *only* in the JSON attrs and not in the HTML is
    purely cosmetic (spacer height, cover dim ratio, embed `"type"`) and
    is not needed for a content model — verified against every `wp:*`
    block type actually present in the archive (see the package README's
    "Gutenberg block coverage" table).
  - `[caption]` / `[gallery]` shortcode placeholders, after
    `shortcodes.preprocess_shortcodes` rewrites them into
    `<now-caption>` / `<now-gallery>` elements.

Design: a single recursive walker coalesces runs of inline content (bare
text + `<em>`/`<strong>`/`<a>`/...) into `paragraph` blocks, and dispatches
true block-level tags to dedicated handlers. Nothing is dropped without
being counted in `stats` — see `models.py` for the schema and the
per-reason breakdown this module writes into `stats`.
"""

from __future__ import annotations

import html as html_module
import re
from typing import Any

import lxml.html
from lxml import etree

from now_content_clean.embeds import classify_provider

Block = dict[str, Any]

_BARE_URL_RE = re.compile(r"^(https?://\S+)$")

# Tags that, when found in "block position" (a direct child of the
# fragment root or of a transparent container), are coalesced into a
# paragraph run instead of becoming their own block — they are inline
# formatting, not structure.
INLINE_TAGS = {
    "span", "em", "strong", "b", "i", "u", "mark", "small", "sup", "sub",
    "br", "code", "s", "del", "ins", "wbr", "time", "abbr", "font", "a",
    "cite", "q", "kbd", "var", "strike", "big", "tt", "label",
}

# Tags with zero reader-visible text — dropped, always counted.
_NON_VISIBLE_TAGS = {"script", "style", "noscript", "svg"}

# Document-fragment noise sometimes pasted verbatim into post_content by a
# past copy/paste (a handful of articles literally contain `<html>`,
# `<meta charset="utf-8" />`, `<head>`/`<body>`). None of these carry
# content of their own; strip the tag, keep whatever real text/markup is
# around it.
_DOC_NOISE_RE = re.compile(r"</?(?:html|head|body)\b[^>]*>|<meta\b[^>]*/?>", re.IGNORECASE)


def strip_document_noise(fragment_html: str) -> str:
    return _DOC_NOISE_RE.sub("", fragment_html)


def _tostring(el) -> str:
    return etree.tostring(el, encoding="unicode", with_tail=False)


def serialize_children(el) -> str:
    parts = [el.text or ""]
    for child in el:
        if isinstance(child.tag, str):
            parts.append(_tostring(child))
        parts.append(child.tail or "")
    return "".join(parts)


def outer_html(el) -> str:
    return _tostring(el)


# Tags that render as visible whitespace — a line break or a block boundary.
# When markup is flattened to plain text these must contribute a separator, or
# the words either side are welded together:
#     "...during the<br>colonial period."  ->  "...during thecolonial period."
#
# Pure inline formatting (<b>, <i>, <span>, <a>, <em>, ...) is deliberately NOT
# in this set: "<b>bold</b>text" genuinely renders as "boldtext", so inserting a
# space there would corrupt the text rather than repair it. lxml's
# text_content() concatenates text nodes with no separator at all, which is
# correct for the inline case and wrong for this one.
_WHITESPACE_RENDERING_TAGS = frozenset({
    "br", "hr", "p", "div", "li", "ul", "ol", "tr", "td", "th", "table",
    "h1", "h2", "h3", "h4", "h5", "h6", "blockquote", "figcaption", "figure",
    "section", "article", "header", "footer", "pre", "dd", "dt", "dl",
})


def _text_preceding(el) -> str:
    """Visible text immediately before `el` — a previous sibling's tail, or
    the parent's leading text when `el` is the first child."""
    prev = el.getprevious()
    if prev is not None:
        return prev.tail or ""
    parent = el.getparent()
    return (parent.text or "") if parent is not None else ""


def _next_visible_char(el) -> str:
    """First character that will follow `el` once the tree is flattened.

    Not the same as `el.tail`: the following text often lives on an ancestor's
    tail instead, e.g. `"contact:<br></strong> +62"` — the `<br>` has no tail
    at all, and the space belongs to `</strong>`. Checking only `el.tail` there
    inserts a boundary that is already present, yielding a double space.
    """
    node = el
    while node is not None:
        tail = node.tail or ""
        if tail:
            return tail[0]
        nxt = node.getnext()
        while nxt is not None:
            if isinstance(nxt.tag, str):
                txt = nxt.text_content()
                if txt:
                    return txt[0]
            t = nxt.tail or ""
            if t:
                return t[0]
            nxt = nxt.getnext()
        node = node.getparent()
    return ""


def apply_render_boundaries(root) -> None:
    """Insert a single space wherever a whitespace-rendering element would
    otherwise weld two words together once the tree is flattened to text.

    Must be applied on BOTH sides of the content-loss metric — the input and
    output sides each flatten markup, and if only one of them inserts
    boundaries the metric reports a phantom delta.
    """
    for el in root.iter():
        if not isinstance(el.tag, str):
            continue
        if el.tag.lower() not in _WHITESPACE_RENDERING_TAGS:
            continue
        tail = el.tail or ""
        # An ancestor's boundary lands at the same textual position as ours
        # when we are its last child with no tail of our own — e.g.
        # "<figcaption>…Gallery.<br></figcaption>". Inserting on both yields a
        # DOUBLE space. Defer to the ancestor, which covers the same position.
        # (Found by QA.2 in 10 real articles.)
        if not tail:
            parent = el.getparent()
            if (
                parent is not None
                and isinstance(parent.tag, str)
                and parent.tag.lower() in _WHITESPACE_RENDERING_TAGS
                and len(parent) and parent[-1] is el
            ):
                continue
        # The boundary belongs after the element's own content. Void elements
        # like <br> have none, so fall back to whatever precedes them.
        own = el.text_content()
        left = own if own else _text_preceding(el)
        # Only insert when a boundary is genuinely missing on both sides, so
        # already-spaced occurrences stay byte-identical (no double spaces).
        # The right-hand side must look ahead through the flattened stream,
        # not just at el.tail — see _next_visible_char.
        right = _next_visible_char(el)
        if left and not left[-1:].isspace() and not right[:1].isspace():
            el.tail = " " + tail


def strip_tags_text(fragment_html: str) -> str:
    if not fragment_html:
        return ""
    wrapper = lxml.html.fragment_fromstring(fragment_html, create_parent="div")
    apply_render_boundaries(wrapper)
    return wrapper.text_content()


def _figcaption_el_for_img(img):
    """The `<figcaption>` element (if any) that belongs to this image —
    its own wrapping `<figure>`'s direct `<figcaption>` child. Returning
    the *element* (not just its text) lets callers track exactly which
    figcaption has already been used as a caption, so a `<figure>` with
    other, unrelated `<figcaption>` siblings never has that same caption
    text emitted a second time as a stray paragraph."""
    parent = img.getparent()
    if parent is not None and parent.tag == "a":
        parent = parent.getparent()
    if parent is not None and parent.tag == "figure":
        return parent.find("figcaption")
    return None


def _figcaption_text(fc) -> str | None:
    if fc is None:
        return None
    return strip_tags_text(serialize_children(fc)).strip() or None


def _image_block_from_img(img) -> Block:
    src = img.get("src") or img.get("data-src") or img.get("data-lazy-src") or ""
    alt = img.get("alt") or ""
    href = None
    parent = img.getparent()
    if parent is not None and parent.tag == "a":
        href = parent.get("href")
    caption = _figcaption_text(_figcaption_el_for_img(img))
    return {"type": "image", "media_ref": src, "alt": alt, "caption": caption, "href": href}


def _paragraph_block(el, stats) -> list[Block]:
    inner = serialize_children(el)
    text_only = strip_tags_text(inner).strip()
    imgs = list(el.iter("img"))
    if imgs and not text_only:
        return [_image_block_from_img(img) for img in imgs]
    if not text_only:
        stats["dropped_empty"] = stats.get("dropped_empty", 0) + 1
        return []
    return [{"type": "paragraph", "html": inner}]


def _heading_block(el, stats) -> list[Block]:
    level = int(el.tag[1])
    inner = serialize_children(el)
    text = strip_tags_text(inner).strip()
    if not text:
        stats["dropped_empty"] = stats.get("dropped_empty", 0) + 1
        return []
    return [{"type": "heading", "level": level, "text": text, "html": inner}]


def _list_block(el, stats) -> list[Block]:
    ordered = el.tag == "ol"
    items = [serialize_children(li) for li in el.findall("li")]
    items = [i for i in items if strip_tags_text(i).strip() or "<img" in i]
    if not items:
        return []
    return [{"type": "list", "ordered": ordered, "items": items}]


def _quote_block(el, stats) -> list[Block]:
    cite_el = el.find("cite")
    cite_text = strip_tags_text(serialize_children(cite_el)).strip() if cite_el is not None else None
    parts = [el.text or ""]
    for child in el:
        if child is cite_el:
            continue
        if isinstance(child.tag, str):
            parts.append(_tostring(child))
        parts.append(child.tail or "")
    inner = "".join(parts)
    if not strip_tags_text(inner).strip() and not cite_text:
        stats["dropped_empty"] = stats.get("dropped_empty", 0) + 1
        return []
    return [{"type": "quote", "html": inner, "cite": cite_text}]


def _hr_block(el, stats) -> list[Block]:
    return [{"type": "separator"}]


def _iframe_block(el, stats) -> list[Block]:
    src = el.get("src") or ""
    return [{"type": "embed", "provider": classify_provider(src), "url": src}]


def _table_block(el, stats) -> list[Block]:
    stats.setdefault("unhandled_tags", {})
    stats["unhandled_tags"]["table"] = stats["unhandled_tags"].get("table", 0) + 1
    return [{"type": "raw_html", "html": outer_html(el), "reason": "unhandled_tag:table"}]


def _drop_non_visible(el, stats) -> list[Block]:
    stats["dropped_non_visible"] = stats.get("dropped_non_visible", 0) + 1
    return []


def _now_caption_block(el, stats) -> list[Block]:
    imgs = el.findall(".//img")
    caption_text = strip_tags_text(serialize_children(el)).strip() or None
    if not imgs:
        if caption_text:
            return [{"type": "paragraph", "html": serialize_children(el)}]
        return []
    if len(imgs) == 1:
        block = _image_block_from_img(imgs[0])
        block["caption"] = caption_text
        return [block]
    images = []
    for img in imgs:
        b = _image_block_from_img(img)
        del b["type"]
        images.append(b)
    return [{"type": "gallery", "images": images, "caption": caption_text}]


def _now_gallery_block(el, stats) -> list[Block]:
    ids_raw = el.get("data-ids", "")
    ids = [i.strip() for i in ids_raw.split(",") if i.strip()]
    stats["gallery_shortcode_ids_only"] = stats.get("gallery_shortcode_ids_only", 0) + 1
    # No inline URLs in a [gallery ids="..."] shortcode — only WP attachment
    # IDs. Content-clean cannot resolve those to media URLs (that's E1.3's
    # job against the attachment table); emit the ids so the loader can.
    return [{"type": "gallery", "images": [], "ids": ids}]


def _columns_block(el, stats) -> list[Block]:
    columns = []
    for child in el:
        if isinstance(child.tag, str) and child.tag == "div" and "wp-block-column" in (child.get("class") or ""):
            columns.append(blocks_from_children(child, stats))
    if not columns:
        return blocks_from_children(el, stats)
    return [{"type": "columns", "columns": columns}]


def _div_block(el, stats) -> list[Block]:
    classes = el.get("class") or ""
    if "wp-block-spacer" in classes:
        stats["dropped_decorative"] = stats.get("dropped_decorative", 0) + 1
        return []
    if "wp-block-columns" in classes:
        return _columns_block(el, stats)
    return blocks_from_children(el, stats)


def _figure_block(el, stats) -> list[Block]:
    """A handful of pre-Gutenberg articles abuse `<figure>`/`<figcaption>`
    as a generic layout wrapper — a `<figure>` containing a genuinely
    captioned nested image *and* a second, unrelated `<figcaption>` that
    holds a full paragraph of body text. Handling only the "primary"
    purpose (the image) and returning would silently drop that second
    figcaption's content, so any direct `<figcaption>` child not actually
    used as a caption is recursed and appended, never dropped."""
    text_only = strip_tags_text(serialize_children(el)).strip()
    imgs = el.findall(".//img")
    bq = el.find(".//blockquote")
    tbl = el.find(".//table")
    direct_figcaptions = el.findall("figcaption")
    consumed: list = []  # figcaption elements already used as a caption

    def mark_consumed(fc) -> None:
        if fc is not None and any(fc is c for c in direct_figcaptions):
            consumed.append(fc)

    def first_unconsumed():
        for fc in direct_figcaptions:
            if not any(fc is c for c in consumed):
                return fc
        return None

    result: list[Block] = []

    if imgs:
        if len(imgs) == 1:
            img = imgs[0]
            block = _image_block_from_img(img)  # already grabs its own figcaption, if any
            mark_consumed(_figcaption_el_for_img(img))
            if not block["caption"]:
                leftover = first_unconsumed()
                if leftover is not None:
                    block["caption"] = _figcaption_text(leftover)
                    mark_consumed(leftover)
            result.append(block)
        else:
            images = []
            for img in imgs:
                b = _image_block_from_img(img)
                mark_consumed(_figcaption_el_for_img(img))
                del b["type"]
                images.append(b)
            cap = None
            leftover = first_unconsumed()
            if leftover is not None:
                cap = _figcaption_text(leftover)
                mark_consumed(leftover)
            result.append({"type": "gallery", "images": images, "caption": cap})
    elif bq is not None:
        result.extend(_quote_block(bq, stats))
    elif (m := (_BARE_URL_RE.match(text_only) if text_only else None)):
        result.append({"type": "embed", "provider": classify_provider(m.group(1)), "url": m.group(1)})
    elif tbl is not None:
        result.extend(_table_block(tbl, stats))
    else:
        # Unknown figure variant (e.g. a bare <figure> with only text) —
        # recurse transparently rather than dropping it.
        return blocks_from_children(el, stats)

    for fc in direct_figcaptions:
        if any(fc is c for c in consumed):
            continue
        result.extend(blocks_from_children(fc, stats))

    return result


BLOCK_HANDLERS = {
    "h1": _heading_block, "h2": _heading_block, "h3": _heading_block,
    "h4": _heading_block, "h5": _heading_block, "h6": _heading_block,
    "p": _paragraph_block,
    "ul": _list_block, "ol": _list_block,
    "blockquote": _quote_block,
    "hr": _hr_block,
    "figure": _figure_block,
    "img": lambda el, stats: [_image_block_from_img(el)],
    "iframe": _iframe_block,
    "table": _table_block,
    "now-caption": _now_caption_block,
    "now-gallery": _now_gallery_block,
    "script": _drop_non_visible, "style": _drop_non_visible,
    "noscript": _drop_non_visible, "svg": _drop_non_visible,
    "div": _div_block, "center": _div_block, "section": _div_block,
    "article": _div_block,
    # A bare/orphan <figcaption> (not consumed by a `<figure>` handler
    # above) is treated as a transparent wrapper — its content still
    # flows through the normal walker rather than being flagged unknown.
    "figcaption": lambda el, stats: blocks_from_children(el, stats),
}


def blocks_from_children(container_el, stats) -> list[Block]:
    """Walk the direct children of `container_el`, coalescing inline runs
    into paragraphs and dispatching block-level tags."""
    blocks: list[Block] = []
    pending: list[str] = []

    def flush() -> None:
        if not pending:
            return
        raw = "".join(pending)
        pending.clear()
        text_only = strip_tags_text(raw).strip()
        if not text_only:
            if raw.strip():
                stats["dropped_empty"] = stats.get("dropped_empty", 0) + 1
            return
        m = _BARE_URL_RE.match(text_only)
        if m:
            blocks.append({"type": "embed", "provider": classify_provider(text_only), "url": text_only})
            return
        blocks.append({"type": "paragraph", "html": raw.strip()})

    def add_text(txt: str | None) -> None:
        if txt:
            pending.append(html_module.escape(txt, quote=False))

    add_text(container_el.text)
    for child in container_el:
        if not isinstance(child.tag, str):
            # Comment / processing-instruction node: no visible text.
            add_text(child.tail)
            continue
        tag = child.tag.lower()
        if tag in BLOCK_HANDLERS:
            flush()
            blocks.extend(BLOCK_HANDLERS[tag](child, stats))
        else:
            if tag not in INLINE_TAGS:
                stats.setdefault("unhandled_tags", {})
                stats["unhandled_tags"][tag] = stats["unhandled_tags"].get(tag, 0) + 1
            pending.append(_tostring(child))
        add_text(child.tail)
    flush()
    return blocks


def blocks_from_fragment(fragment_html: str, stats: dict) -> list[Block]:
    if not fragment_html or not fragment_html.strip():
        return []
    cleaned = strip_document_noise(fragment_html)
    root = lxml.html.fragment_fromstring(cleaned, create_parent="div")
    return blocks_from_children(root, stats)
