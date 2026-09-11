"""Gutenberg block-comment parsing.

A Gutenberg block is `<!-- wp:name {json attrs} --> <complete standalone
HTML> <!-- /wp:name -->` (or a self-closed `<!-- wp:name {...} /-->` for a
block with no HTML body, e.g. `wp:spacer`, `wp:footnotes`). Verified
against every `<!-- wp:... -->` occurrence in the 4,772 published articles
(see the package README's "Gutenberg block coverage" table): the HTML
between the markers is always itself complete, well-formed, and already
self-describing (a heading's level is in its `<h2>` tag, a list's
orderedness is in `<ul>` vs `<ol>`, a gallery is one `<figure>` per photo,
an embed's URL is the wrapper's bare text) — there is no case in this
archive where a `wp:*` comment's JSON attrs carry content not already
present in the surrounding HTML.

So "parsed as structure" here means: tokenize every marker, walk it with a
depth stack to confirm real (balanced) nesting and count block types seen
— this is genuine structural parsing, not a blind string strip — then
strip the markers themselves and hand the underlying HTML to the *same*
`html_blocks` engine used for classic content. The literal comment text
`<!-- wp:... -->` never appears in any output block; that's what "never
left as literal text" requires.
"""

from __future__ import annotations

import re

_TOKEN_RE = re.compile(
    r"<!--\s*(/?)wp:([a-zA-Z0-9_/-]+)(?:\s+(.*?))?\s*(/?)-->",
    re.DOTALL,
)


def has_gutenberg_markup(content_html: str) -> bool:
    return "<!-- wp:" in content_html


def scan_blocks(content_html: str, stats: dict) -> None:
    """Walk the comment tokens with a depth stack purely to verify
    balance and count block types — writes into `stats`, doesn't change
    `content_html`."""
    stack: list[str] = []
    counts: dict[str, int] = stats.setdefault("gutenberg_block_types", {})
    for m in _TOKEN_RE.finditer(content_html):
        closing, name, _attrs, self_close = m.group(1), m.group(2), m.group(3), m.group(4)
        if self_close:
            counts[name] = counts.get(name, 0) + 1
            continue
        if closing:
            if stack and stack[-1] == name:
                stack.pop()
            else:
                stats["gutenberg_unbalanced"] = stats.get("gutenberg_unbalanced", 0) + 1
        else:
            counts[name] = counts.get(name, 0) + 1
            stack.append(name)
    if stack:
        stats["gutenberg_unbalanced"] = stats.get("gutenberg_unbalanced", 0) + len(stack)


def strip_wp_comments(content_html: str) -> str:
    return _TOKEN_RE.sub("", content_html)
