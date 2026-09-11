"""Typed shapes for the E1.2 output.

Block schema (documented deviations from the ticket's proposed shape are
called out inline — none of them drop information, they only add fields
or add block types for structural signal the ticket's sketch didn't
enumerate but the real corpus contains, e.g. `wp:columns`, `wp:gallery`,
`wp:separator`).

    {"type": "heading", "level": 2, "text": "...", "html": "..."}
        `text` is the tag-stripped rendition (search/index use). `html`
        is the inner markup verbatim (bold/links/etc. preserved) — added
        so a heading with inline formatting loses nothing.

    {"type": "paragraph", "html": "..."}

    {"type": "image", "media_ref": "...", "alt": "...", "caption": "...",
     "href": "..." | None}
        `media_ref` is the *original* WP src (rewritten later by E1.3).
        `href` is set when the image is wrapped in an `<a href>` (common
        classic-editor pattern: image links out to a full-size version or
        an external site) — additive, not in the ticket's sketch.

    {"type": "gallery", "images": [<image block, minus type>, ...]}
        Added type: `wp:gallery` is 2,312 occurrences across the corpus,
        more common than several types the ticket sketch does list.

    {"type": "list", "ordered": false, "items": ["<html>", ...]}
        Items are inner-HTML strings (not plain text) because list items
        routinely carry `<em>`/`<strong>`/`<a>` — flattening to plain text
        would be silent content loss.

    {"type": "quote", "html": "...", "cite": "..." | None}
        Also used for `wp:pullquote`.

    {"type": "embed", "provider": "youtube", "url": "..."}

    {"type": "separator"}
        Added type for `<hr>` / `wp:separator` (1,126 occurrences) — a
        real structural element, not decoration to discard.

    {"type": "columns", "columns": [[<block>, ...], [<block>, ...]]}
        Added type for `wp:columns` (251 occurrences) — each inner list is
        one column's block sequence.

    {"type": "raw_html", "html": "...", "reason": "unhandled_tag:table"}
        Escape hatch for anything not recognised, or recognised-but-not
        worth structuring (e.g. `wp:table`). `reason` is free text used
        only for the unhandled-constructs report; always present.

`wp:spacer` and empty paragraphs (`<p></p>`, `<p>&nbsp;</p>`) are dropped
because they carry zero visible text — counted in `stats.dropped_empty`,
never silently vanished from the report.

Links and inline `wp-content/uploads` references are extracted from the
*original* `content_html` string (not from the block tree) so their
`offset` is exact and independent of how the block builder chose to
group/flatten markup.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class LinkRef:
    href: str
    text: str
    rel: str | None
    offset: int  # char offset of the '<a' in the original content_html
    is_upload: bool = False


@dataclass
class UploadRef:
    url: str
    offset: int  # char offset of the match in the original content_html
    context: str  # "img_src" | "a_href" | "other"


@dataclass
class CleanResult:
    wp_id: int
    blocks: list[dict[str, Any]]
    links: list[LinkRef]
    uploads: list[UploadRef]
    stats: dict[str, Any] = field(default_factory=dict)
