"""Shortcode handling — `[caption]` (17 occurrences archive-wide) and
`[gallery]` (0 in the sample, but the ticket calls it out explicitly, so
it's handled defensively).

Strategy: rewrite well-formed shortcodes into placeholder HTML elements
*before* the HTML parser ever sees the string, so `html_blocks.py` can
treat them like any other element. Real-world WP content is messy —
several `[caption]` instances in this archive are HTML-entity-escaped
(`&quot;` instead of `"`) and/or have no matching `[/caption]` because the
shortcode spans a broken `<p>` boundary from a bad copy-paste. For those we
never invent structure we can't verify: we just strip the bracket tokens
and let the surrounding HTML (which is intact) flow through the normal
parser. Either way, zero visible text is removed — only the WP-specific
`[...]` markup tokens are.
"""

from __future__ import annotations

import html
import re

# Well-formed: [caption id="..." align="..." width="..."]<content>[/caption]
# Attribute quotes may be real quotes or HTML-entity-escaped ones (&quot;),
# and the shortcode itself may or may not be HTML-entity-escaped as a
# whole (`[caption id=&quot;x&quot;...]`) if it was typed into the old
# TinyMCE "text" view. DOTALL because captions commonly wrap an <img>.
_CAPTION_RE = re.compile(
    r"\[caption([^\]]*)\](.*?)\[/caption\]",
    re.IGNORECASE | re.DOTALL,
)
_GALLERY_RE = re.compile(r"\[gallery([^\]]*)\]", re.IGNORECASE)

_ATTR_RE = re.compile(r"""(\w[\w-]*)\s*=\s*(?:"([^"]*)"|&quot;([^&]*)&quot;|'([^']*)')""")

# Fallback for any [caption ...] / [/caption] token left over after the
# paired regex above (i.e. malformed/unpaired instances) — strip the
# marker only, keep everything else.
_STRAY_CAPTION_OPEN_RE = re.compile(r"\[caption[^\]]*\]", re.IGNORECASE)
_STRAY_CAPTION_CLOSE_RE = re.compile(r"\[/caption\]", re.IGNORECASE)
_STRAY_GALLERY_RE = re.compile(r"\[gallery[^\]]*\]", re.IGNORECASE)


def _parse_attrs(raw_attrs: str) -> dict[str, str]:
    attrs = {}
    for m in _ATTR_RE.finditer(html.unescape(raw_attrs)):
        key = m.group(1)
        val = next(g for g in m.groups()[1:] if g is not None)
        attrs[key] = val
    return attrs


def preprocess_shortcodes(content_html: str, stats: dict) -> str:
    """Replace well-formed shortcodes with placeholder elements the HTML
    parser understands; strip anything left unpaired."""

    def caption_sub(m: re.Match) -> str:
        attrs = _parse_attrs(m.group(1))
        inner = m.group(2)
        stats["shortcode_caption"] = stats.get("shortcode_caption", 0) + 1
        wid = attrs.get("id", "")
        return f'<now-caption data-attachment-id="{html.escape(wid)}">{inner}</now-caption>'

    out = _CAPTION_RE.sub(caption_sub, content_html)

    def gallery_sub(m: re.Match) -> str:
        attrs = _parse_attrs(m.group(1))
        stats["shortcode_gallery"] = stats.get("shortcode_gallery", 0) + 1
        ids = html.escape(attrs.get("ids", ""))
        return f'<now-gallery data-ids="{ids}"></now-gallery>'

    out = _GALLERY_RE.sub(gallery_sub, out)

    # Anything left is malformed/unpaired — strip the token, keep content.
    def stray(pattern: re.Pattern, key: str, text: str) -> str:
        n = len(pattern.findall(text))
        if n:
            stats[key] = stats.get(key, 0) + n
        return pattern.sub("", text)

    out = stray(_STRAY_CAPTION_OPEN_RE, "shortcode_caption_stray", out)
    out = stray(_STRAY_CAPTION_CLOSE_RE, "shortcode_caption_stray", out)
    out = stray(_STRAY_GALLERY_RE, "shortcode_gallery_stray", out)
    return out
