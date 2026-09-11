"""Small, dependency-free text helpers used only for *bookkeeping* strings
(slugs, filenames, a one-line dek fallback) — never for parsing the article
body. `content_html` -> `body_blocks` is exclusively `now_content_clean`'s
job (ARCHITECTURE.md §6: "Use it; do not re-parse HTML").

`strip_tags_light` exists only because a handful of source fields that are
*not* the article body (the native WP excerpt, Yoast's `_yoast_wpseo_metadesc`)
occasionally carry a stray tag or an HTML entity even though they're
conceptually plain text. Reaching for the full E1.2 block pipeline for a
one-line meta string would be the wrong tool; a tag-strip + entity-unescape
is deliberately the full extent of "HTML handling" this module does.
"""

from __future__ import annotations

import html
import re
import statistics
import unicodedata

_TAG_RE = re.compile(r"<[^>]*>")
_WS_RE = re.compile(r"\s+")
_SLUG_STRIP_RE = re.compile(r"[^a-z0-9]+")


def strip_tags_light(value: str | None) -> str | None:
    if not value:
        return None
    text = html.unescape(_TAG_RE.sub(" ", value))
    text = _WS_RE.sub(" ", text).strip()
    return text or None


def slugify(value: str) -> str:
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    value = value.lower()
    value = _SLUG_STRIP_RE.sub("-", value)
    return value.strip("-")


def basename(path_or_url: str) -> str:
    """Last path segment, ignoring query strings. Good enough for WP media
    paths/URLs; not a general-purpose URL parser."""
    cleaned = path_or_url.split("?", 1)[0].rstrip("/")
    return cleaned.rsplit("/", 1)[-1] if cleaned else path_or_url


def summarize_content_loss(loss_pcts: list[float]) -> dict[str, float | None]:
    """Median/p95/max of a batch of `now_content_clean` `loss_pct` values.

    Pulled out as a pure function (no DB, no `clean_article` call) so it can
    be unit-tested directly — this package has no DB-backed test harness for
    `articles`/`events` (`now_test` carries no Payload schema; see
    `tests/test_load_orgs.py`'s docstring for the one table that does have
    one). Mirrors `load_events.py`'s inline percentile logic exactly so the
    two reports are comparable; `load_articles.py` is the only caller today,
    but any future stage aggregating the same shape can reuse this instead
    of re-deriving it.
    """
    if not loss_pcts:
        return {"median": None, "p95": None, "max": None}
    ordered = sorted(loss_pcts)
    return {
        "median": round(statistics.median(loss_pcts), 3),
        "p95": round(ordered[int(len(ordered) * 0.95)], 3),
        "max": round(max(loss_pcts), 3),
    }
