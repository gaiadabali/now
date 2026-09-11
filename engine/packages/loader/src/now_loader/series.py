"""`articles.series_key` derivation — ARCHITECTURE.md §6 known issue:
"New Restaurants in Jakarta 2024 / 2025 [Updated]" style annual reposts.

Deliberately conservative. This is a *loader*, not the classifier (E2.1) or
the quality/series pass (E2.6) — it must not invent clusters. The rule:

  1. Strip a trailing/embedded "[Updated]" / "(Updated)" marker.
  2. Strip a 4-digit year token (1950-2049 — wide enough for any real
     publish year in the archive, narrow enough to not eat unrelated
     4-digit numbers like a street address).
  3. Slugify what's left.
  4. Only assign the resulting key to an article if *at least one other*
     article in the same batch reduces to the same key. A singleton
     (title happens to end in a year but nothing else in the corpus
     matches) gets `series_key = None`, not a lonely cluster of one.

Run against the full 4,772-article corpus this finds 3 real series (7
articles) — e.g. "New Restaurants in Jakarta {2024,2025,2026}: Latest
Openings [Updated]" all resolve to `new-restaurants-in-jakarta-latest-openings`.
That is intentionally small and high-precision; broader series clustering
(fuzzy titles, body similarity) is E2.6's job, not this loader's.
"""

from __future__ import annotations

import re
from collections import Counter

from now_loader.textutil import slugify

_YEAR_RE = re.compile(r"\b(19[5-9][0-9]|20[0-4][0-9])\b")
_UPDATED_RE = re.compile(r"[\[\(]?\s*updated\s*[\]\)]?", re.IGNORECASE)
_TRAILING_PUNCT_RE = re.compile(r"\s{2,}")

MIN_CANDIDATE_LEN = 8


def _candidate_key(title: str) -> str | None:
    if not _YEAR_RE.search(title):
        return None
    stripped = _UPDATED_RE.sub("", title)
    stripped = _YEAR_RE.sub("", stripped)
    stripped = _TRAILING_PUNCT_RE.sub(" ", stripped).strip(" :,-")
    key = slugify(stripped)
    if len(key) < MIN_CANDIDATE_LEN:
        return None
    return key


def derive_series_keys(titles_by_wp_id: dict[int, str]) -> dict[int, str]:
    """Batch derivation: only articles whose candidate key recurs (>=2
    articles) get a `series_key`. Returns {wp_id: series_key} — wp_ids not
    present in the result should have `series_key = NULL`."""
    candidates: dict[int, str] = {}
    for wp_id, title in titles_by_wp_id.items():
        key = _candidate_key(title)
        if key:
            candidates[wp_id] = key

    counts = Counter(candidates.values())
    return {wp_id: key for wp_id, key in candidates.items() if counts[key] >= 2}
