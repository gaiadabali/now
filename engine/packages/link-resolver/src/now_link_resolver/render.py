"""The renderer: `body_blocks` + resolved mentions -> `body_blocks` with
every `<span data-place="...">` reference rewritten per its tier.

Pure and side-effect-free by construction: it reads `body_blocks` (never
mutated in place -- a deep copy is built and returned) and a
`dict[place_id, LinkDecision]` already computed by `resolver.py`, and
performs zero I/O of its own. Calling it twice on the same inputs
produces byte-identical output (idempotent); it never opens a DB
connection, writes a click, or has any observable effect beyond its
return value. Click logging is a deliberately separate call
(`clicks.py`), invoked only when a reader actually clicks a paid link --
never from render.

Per ARCHITECTURE.md Sec.11's own example, the entity reference an article
carries is an inline marker already present in `body_blocks`:

    ... stayed at <span data-place="viceroy-bali">The Viceroy Bali</span> ...

`place_id` in that marker is whatever the mention resolution used as its
key (a real place id once E2.3 populates `place_mentions`; a synthetic
id in this ticket's tests). This module only rewrites that marker -- it
does not decide the tier; `resolver.py` already did that.
"""

from __future__ import annotations

import copy
import re
from html import escape

from now_link_resolver.types import LinkDecision

_MENTION_RE = re.compile(r'<span\s+data-place="([^"]+)"[^>]*>(.*?)</span>', re.DOTALL)

# Every body_blocks field that can carry inline HTML/text with a mention
# marker in it, per ARCHITECTURE.md Sec.5's shipped block schema.
_INLINE_HTML_FIELDS = ("html", "text", "caption")


def _render_span(match: re.Match[str], decisions: dict[str, LinkDecision]) -> str:
    place_id, inner = match.group(1), match.group(2)
    decision = decisions.get(place_id)
    if decision is None:
        # No resolution supplied for this marker -- fail closed to plain
        # text rather than leaving an unresolved <span> in reader-facing
        # HTML or guessing at a tier.
        return inner

    if decision.tier == "free":
        return inner

    if decision.tier == "listed":
        return f'<a href="{escape(decision.href or "", quote=True)}">{inner}</a>'

    # paid -- rel="sponsored" is emitted as a LITERAL here, deliberately, rather
    # than read from `decision.rel`.
    #
    # `LinkDecision.rel` is already a computed property with no setter, and QA.5
    # confirmed both `dataclasses.replace(..., rel=...)` and
    # `object.__setattr__` fail to override it. But it also found the one
    # remaining hole: this renderer duck-types on the decision, so a SUBCLASS
    # overriding `rel` would have been rendered verbatim --
    #     class Evil(LinkDecision):
    #         @property
    #         def rel(self): return "definitely-not-sponsored"
    # ...produced exactly that in the output. No such subclass exists (the only
    # constructor call sites in the tree are the five in resolver.py), so it was
    # latent rather than live -- but "no caller does this today" is a weak
    # guarantee for a commercial rule, and Google penalises the domain, not the
    # class hierarchy.
    #
    # Not consulting the object at all removes the override surface entirely:
    # for tier == "paid" this function cannot emit anything but rel="sponsored".
    assert decision.tier == "paid"
    badge = ""
    if decision.show_badge:
        label = escape(decision.badge_label or "Partner", quote=True)
        badge = f'<span class="badge badge--partner">{label}</span>'
    partner_ref = escape(decision.org_id or decision.partnership_id or "", quote=True)
    return (
        f'<a href="{escape(decision.href or "", quote=True)}" '
        f'rel="sponsored" '
        f'data-partner="{partner_ref}" '
        f'data-partnership="{escape(decision.partnership_id or "", quote=True)}">{inner}</a>'
        f"{badge}"
    )


def _rewrite_text(value: str, decisions: dict[str, LinkDecision]) -> str:
    return _MENTION_RE.sub(lambda m: _render_span(m, decisions), value)


def _walk(node: object, decisions: dict[str, LinkDecision]) -> object:
    if isinstance(node, dict):
        out = {}
        for key, value in node.items():
            if key in _INLINE_HTML_FIELDS and isinstance(value, str):
                out[key] = _rewrite_text(value, decisions)
            elif key == "items" and isinstance(value, list):
                # `list` blocks: {"type":"list","items":["…"]} -- each item
                # is plain inline text/HTML, not a nested block.
                out[key] = [
                    _rewrite_text(item, decisions) if isinstance(item, str) else _walk(item, decisions)
                    for item in value
                ]
            else:
                out[key] = _walk(value, decisions)
        return out
    if isinstance(node, list):
        return [_walk(item, decisions) for item in node]
    if isinstance(node, str):
        return node
    return node


def render_body_blocks(
    body_blocks: list[dict],
    decisions: dict[str, LinkDecision],
) -> list[dict]:
    """Return a new `body_blocks` list with every `data-place` marker
    resolved. Never mutates its inputs (`copy.deepcopy` up front); never
    performs I/O. Safe to call once per request or a thousand times --
    the output only ever depends on `body_blocks` and `decisions`."""
    blocks = copy.deepcopy(body_blocks)
    return [_walk(block, decisions) for block in blocks]  # type: ignore[misc]
