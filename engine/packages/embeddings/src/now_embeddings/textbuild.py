"""Builds the exact string that gets embedded, per entity type, and its
sha256 hash (the idempotency key -- see `store.py`).

ARCHITECTURE.md §6 specifies the ingest recipe as `embed: title + dek +
facets + body`. **Facets, `primary_type` and `format` are all NULL right
now** (E2.1 classification is blocked on a human taxonomy review -- see the
E2.4 task brief and PROGRESS.md Wave 4). This module embeds on
title+dek+body only, today, and picks up facets/type/format automatically
the moment E2.1 populates them -- with no code change here. That is the
whole reason `text_hash` exists (see `store.py`): the hash is computed over
whatever fields are non-null *right now*, so the day E2.1 lands, every
article's hash changes and the next `now-embeddings backfill` run
re-embeds exactly the rows whose input text actually changed, and nothing
else.

**Truncation, stated plainly**: `BAAI/bge-small-en-v1.5` (like almost every
BERT-family encoder) has a 512-token context window. The archive's median
article is ~4,800 characters -- several times that window. This module
does not chunk-and-average (adds real complexity for a v1 pipeline) or
silently let the tokenizer truncate wherever it likes (opaque, and title
could get pushed out of the window on a long `dek`). Instead it builds
`title + dek + type/format (if present) + body[:BODY_CHAR_BUDGET]`
explicitly, so the truncation point is a documented, inspectable design
choice rather than an implicit tokenizer behaviour. `BODY_CHAR_BUDGET`
chars of English prose is comfortably inside the 512-token window with
room for title/dek, per a rough 4-chars/token heuristic.

Consequence, stated honestly: **long-tail body content past the first
~1,600 characters does not influence an article's embedding.** For a
magazine where articles front-load their topic (the who/what/where is
almost always in the opening paragraphs), this is a reasonable v1
trade-off, not a hidden defect -- but it is a real limitation worth
revisiting (chunk + mean-pool, or a long-context model) if Row 3 "similar"
quality ever looks like it's missing content that only appears deep in an
article.
"""

from __future__ import annotations

import hashlib

from now_content_clean.metrics import visible_text_out

BODY_CHAR_BUDGET = 1600


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def build_article_text(
    *,
    title: str | None,
    dek: str | None,
    body_blocks: list[dict] | None,
    primary_type: str | None,
    format: str | None,
    facet_labels: list[str] | None = None,
) -> tuple[str, str]:
    """Returns (text, text_hash). `body_blocks` is the exact jsonb array
    E1.2/E1.8 shipped (ARCHITECTURE.md §5) -- reused via
    `now_content_clean.metrics.visible_text_out`, the same "flatten blocks
    to visible text" logic the content-loss metric uses, rather than
    re-parsing block types here."""
    parts: list[str] = []
    if title:
        parts.append(title)
    if dek:
        parts.append(dek)
    if primary_type:
        parts.append(f"type: {primary_type}")
    if format:
        parts.append(f"format: {format}")
    if facet_labels:
        parts.append("facets: " + ", ".join(facet_labels))
    body_text = visible_text_out(body_blocks or [])
    if body_text:
        parts.append(body_text[:BODY_CHAR_BUDGET])
    text = "\n\n".join(parts)
    return text, _hash(text)


def build_place_text(
    *,
    name: str,
    address: str | None,
    area_term: str | None,
    place_type: str | None,
    subtype: str | None,
    price_band: str | None,
    amenities: list[str] | None,
    cuisine: list[str] | None,
    vibe: list[str] | None,
) -> tuple[str, str]:
    """Places have no `body` -- there is no article prose to draw on. The
    text is the structured fields that exist (ARCHITECTURE.md §5 `places`
    columns), which is enough to place a venue near semantically similar
    venues (a rooftop bar near other rooftop bars) even before E2.2 facet
    extraction fills amenities/cuisine/vibe for the loader's F27 sentinel
    rows."""
    parts: list[str] = [name]
    if place_type:
        parts.append(f"type: {place_type}")
    if subtype:
        parts.append(f"subtype: {subtype}")
    if price_band:
        parts.append(f"price: {price_band}")
    if area_term:
        parts.append(f"area: {area_term}")
    if amenities:
        parts.append("amenities: " + ", ".join(sorted(amenities)))
    if cuisine:
        parts.append("cuisine: " + ", ".join(sorted(cuisine)))
    if vibe:
        parts.append("vibe: " + ", ".join(sorted(vibe)))
    if address:
        parts.append(address)
    text = "\n".join(parts)
    return text, _hash(text)


def build_term_text(*, facet_key: str, label: str, slug: str) -> tuple[str, str]:
    """Terms are single vocabulary entries (`now_platform.engine.terms`) --
    the taxonomy facet they belong to plus their human label is the whole
    of what there is to embed (`facets` is used deliberately here as
    context, e.g. "cuisine: japanese" vs. bare "japanese", so a term's
    embedding reflects which axis of the vocabulary it sits on)."""
    text = f"{facet_key}: {label} ({slug})"
    return text, _hash(text)
