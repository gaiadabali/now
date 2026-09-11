"""Outbound-link and inline-upload-reference extraction.

Both scan the *original* `content_html` string directly (not the parsed
block tree) so the reported `offset` is exact and stable regardless of how
blocks.py chooses to group or flatten markup — E1.5 (partner-roster
clustering) and E4.3 (link -> mention conversion) need a byte-accurate
anchor back into the source.
"""

from __future__ import annotations

import html
import re

from now_content_clean.models import LinkRef, UploadRef

_TAG_RE = re.compile(r"<[^>]*>")

# Non-greedy across the whole opening tag, then non-greedy body up to the
# first closing </a> (an <a> can't legally nest another <a>, so this is
# safe even with DOTALL for multi-line anchor text).
_ANCHOR_RE = re.compile(r"<a\b([^>]*)>(.*?)</a>", re.IGNORECASE | re.DOTALL)

_HREF_RE = re.compile(r"""href\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s>]+))""", re.IGNORECASE)
_REL_RE = re.compile(r"""rel\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s>]+))""", re.IGNORECASE)

UPLOADS_RE = re.compile(r"""(["'(]?)([^"'()\s]*wp-content/uploads/[^"'()\s]*)""")


def _strip_tags(fragment: str) -> str:
    return html.unescape(_TAG_RE.sub("", fragment)).strip()


def _first_group(m: re.Match | None) -> str | None:
    if not m:
        return None
    return next((g for g in m.groups() if g is not None), None)


def extract_links(content_html: str) -> list[LinkRef]:
    links: list[LinkRef] = []
    for m in _ANCHOR_RE.finditer(content_html):
        attrs, inner = m.group(1), m.group(2)
        href = _first_group(_HREF_RE.search(attrs))
        if href is None:
            continue  # <a name="..."> style internal anchor, no outbound target
        href = html.unescape(href)
        rel = _first_group(_REL_RE.search(attrs))
        rel = html.unescape(rel) if rel else None
        links.append(
            LinkRef(
                href=href,
                text=_strip_tags(inner),
                rel=rel,
                offset=m.start(),
                is_upload="wp-content/uploads" in href,
            )
        )
    return links


def extract_uploads(content_html: str) -> list[UploadRef]:
    """Every inline `wp-content/uploads` reference, whatever attribute it
    lives in (img src/srcset, a href, background-image: url(...), etc.)."""
    uploads: list[UploadRef] = []
    for m in UPLOADS_RE.finditer(content_html):
        url = html.unescape(m.group(2).rstrip(").,;"))
        # crude context sniff: look a few chars back for the attribute name
        window = content_html[max(0, m.start(2) - 12) : m.start(2)]
        if "src=" in window:
            context = "img_src"
        elif "href=" in window:
            context = "a_href"
        else:
            context = "other"
        uploads.append(UploadRef(url=url, offset=m.start(2), context=context))
    return uploads
