"""Deliverable 3 -- series clustering. ARCHITECTURE.md Sec.8.A: "one
article per series_key per rail", protecting annually-refreshed listicles
("New Restaurants in Jakarta 2024/2025 [Updated]") from competing with
their own old editions forever.

## Method -- deliberately conservative

1. **Normalize** every title: HTML-unescape (some raw titles carry
   un-decoded `&amp;`), lowercase, strip a recognised "this title was
   refreshed" marker (`[Updated]`/`(Updated)`/bare "Updated"), strip
   4-digit years (2015-2029) and ordinal-number tokens ("5th", "1st" --
   the ticket's "ordinal variants", e.g. "5th Annual X"), then collapse
   everything else to single spaces over `[a-z0-9]` only. This last step
   is also what makes mangled-encoding titles cluster correctly without
   any special-casing: a corrupted apostrophe (`Jakarta�s` instead of
   `Jakarta's`) or a missing space (`NOW!Jakarta` instead of `NOW! Jakarta`)
   both collapse to the same run of spaces as clean punctuation would.

2. **Group by normalized signature.** A group of >=2 articles is a
   candidate series.

3. **Classify each candidate group, conservatively:**
   - **Confident series** (auto-clustered): the *original* titles in the
     group actually differ because of a year and/or an "Updated" marker
     -- i.e. there is a real refresh signal, not just an accidental exact
     duplicate. This is `new-restaurants-in-jakarta-latest-openings`,
     `artmoments-jakarta`, and one more this run adds (see the report).
   - **Uncertain** (flagged, never auto-merged): the group's *original*
     titles are identical (or near-identical with no year/Updated signal)
     -- e.g. the same interview title published twice, days or weeks
     apart, in this corpus. That could be a genuine annual-style refresh,
     but it could just as easily be two distinct pieces that happen to
     share a title, or a migration-era duplicate publish. Since "a false
     merge hides good content permanently" (the ticket's own words), these
     are surfaced for a human, not merged.

4. **A secondary, best-effort fuzzy pass** (`find_fuzzy_candidates`) looks
   for near-duplicate titles that *don't* share an exact normalized
   signature (e.g. reworded suffixes) using a word-overlap bucket index +
   `difflib.SequenceMatcher`. This *only* produces additional "uncertain"
   candidates for the report -- it never assigns a `series_key`. High
   recall, zero precision requirement, because the only action it can
   trigger is "a human should look at this."

5. **series_key** is a slug of the normalized signature. **Never
   overwritten**: `assign` only ever updates rows where
   `series_key IS NULL` (see `now_quality.db.assign_series_key`), so a
   pre-existing key (the loader's 2 series) or a prior manual correction
   survives every rerun untouched -- the idempotency the ticket requires.
   Where an existing non-null `series_key` is already present on *some*
   members of a normalized group, new NULL-keyed members of that same
   group are assigned the *existing* key rather than inventing a new one,
   so a manually-seeded series can grow across reruns instead of forking.

6. **Current member**: the member whose title mentions the highest year;
   if no member's title carries a year (e.g. only an "Updated" marker),
   the most recently published member. Recorded in `quality_scores.
   components` (see `now_quality.cli`), not in a new column -- there is
   no schema room for a boolean `is_current` on `articles`.
"""

from __future__ import annotations

import difflib
import html
import re
from dataclasses import dataclass, field

_YEAR_RE = re.compile(r"\b(19|20)\d{2}\b")
_ORDINAL_RE = re.compile(r"\b\d+(st|nd|rd|th)\b", re.IGNORECASE)
_UPDATED_RE = re.compile(r"\[\s*updated\s*\]|\(\s*updated\s*\)|\bupdated\b", re.IGNORECASE)
_NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")
_WS_RE = re.compile(r"\s+")

_STOPWORDS = {
    "the", "a", "an", "in", "at", "of", "to", "for", "and", "on", "with",
    "is", "are", "your", "this", "that",
}


def normalize_title(title: str) -> str:
    text = html.unescape(title or "")
    text = text.lower()
    text = _UPDATED_RE.sub(" ", text)
    text = _YEAR_RE.sub(" ", text)
    text = _ORDINAL_RE.sub(" ", text)
    text = _NON_ALNUM_RE.sub(" ", text)
    return _WS_RE.sub(" ", text).strip()


def extract_years(title: str) -> list[int]:
    return [int(m.group(0)) for m in _YEAR_RE.finditer(title or "")]


def has_refresh_signal(titles: list[str]) -> bool:
    """True if the group's *original* titles actually differ due to a
    year and/or an Updated marker -- the signal that separates a genuine
    annual refresh from an accidental exact-duplicate title."""
    years_seen = {tuple(sorted(extract_years(t))) for t in titles}
    if len(years_seen) > 1:
        return True
    if any(extract_years(t) for t in titles) and any(_UPDATED_RE.search(t) for t in titles):
        return True
    return any(_UPDATED_RE.search(t) for t in titles) and len({t.strip().lower() for t in titles}) > 1


def slugify(text: str) -> str:
    return _WS_RE.sub(" ", text).strip().replace(" ", "-")


@dataclass
class ArticleRow:
    id: int
    title: str
    published_at: str | None  # ISO date string, for display/tie-break
    existing_series_key: str | None = None


@dataclass
class SeriesCluster:
    series_key: str
    normalized: str
    members: list[ArticleRow]
    current_id: int
    confident: bool
    reason: str


@dataclass
class ClusterReport:
    confident: list[SeriesCluster] = field(default_factory=list)
    uncertain: list[SeriesCluster] = field(default_factory=list)
    fuzzy_candidates: list[tuple[ArticleRow, ArticleRow, float]] = field(default_factory=list)


def pick_current(members: list[ArticleRow]) -> ArticleRow:
    def key(m: ArticleRow) -> tuple:
        years = extract_years(m.title)
        best_year = max(years) if years else -1
        return (best_year, m.published_at or "")

    return max(members, key=key)


def cluster_titles(rows: list[ArticleRow]) -> ClusterReport:
    groups: dict[str, list[ArticleRow]] = {}
    for row in rows:
        norm = normalize_title(row.title)
        if not norm:
            continue
        groups.setdefault(norm, []).append(row)

    report = ClusterReport()
    for norm, members in groups.items():
        if len(members) < 2:
            continue
        titles = [m.title for m in members]
        confident = has_refresh_signal(titles)

        # Extend an existing manually/previously-assigned key if any member
        # already carries one, instead of inventing a fresh slug -- keeps a
        # seeded series growing across reruns rather than forking.
        existing_keys = {m.existing_series_key for m in members if m.existing_series_key}
        if len(existing_keys) == 1:
            series_key = next(iter(existing_keys))
        elif len(existing_keys) > 1:
            # Members of the same normalized title already disagree on
            # series_key -- someone made a manual call we shouldn't second
            # guess. Surface as uncertain rather than picking one.
            report.uncertain.append(
                SeriesCluster(
                    series_key="(conflicting existing keys: " + ", ".join(sorted(existing_keys)) + ")",
                    normalized=norm,
                    members=members,
                    current_id=pick_current(members).id,
                    confident=False,
                    reason="members already carry different series_key values -- needs a human decision",
                )
            )
            continue
        else:
            series_key = slugify(norm)

        cluster = SeriesCluster(
            series_key=series_key,
            normalized=norm,
            members=members,
            current_id=pick_current(members).id,
            confident=confident,
            reason=(
                "year and/or [Updated] marker differs across original titles"
                if confident
                else "identical/near-identical titles with no year or Updated signal -- "
                "could be a genuine refresh or an accidental duplicate publish"
            ),
        )
        (report.confident if confident else report.uncertain).append(cluster)

    return report


def _significant_words(norm: str) -> set[str]:
    return {w for w in norm.split() if w not in _STOPWORDS and len(w) > 2}


def find_fuzzy_candidates(
    rows: list[ArticleRow],
    already_grouped_norms: set[str],
    threshold: float = 0.87,
) -> list[tuple[ArticleRow, ArticleRow, float]]:
    """Best-effort near-duplicate finder for titles that don't share an
    exact normalized signature. Report-only (see module docstring) --
    bucketed by shared significant words to keep this well under O(n^2)
    on a ~4.8k-row corpus, then scored with `difflib.SequenceMatcher`."""
    by_norm: dict[str, ArticleRow] = {}
    for row in rows:
        norm = normalize_title(row.title)
        if norm and norm not in already_grouped_norms:
            by_norm.setdefault(norm, row)  # one representative per signature

    buckets: dict[str, list[str]] = {}
    for norm in by_norm:
        for word in _significant_words(norm):
            buckets.setdefault(word, []).append(norm)

    seen_pairs: set[tuple[str, str]] = set()
    candidates: list[tuple[ArticleRow, ArticleRow, float]] = []
    for norm_list in buckets.values():
        if len(norm_list) < 2 or len(norm_list) > 50:
            continue  # a bucket this large is a stopword-like word, not a real signal
        uniq = sorted(set(norm_list))
        for i in range(len(uniq)):
            for j in range(i + 1, len(uniq)):
                pair = (uniq[i], uniq[j])
                if pair in seen_pairs:
                    continue
                seen_pairs.add(pair)
                ratio = difflib.SequenceMatcher(None, uniq[i], uniq[j]).ratio()
                if ratio >= threshold:
                    candidates.append((by_norm[uniq[i]], by_norm[uniq[j]], round(ratio, 3)))

    candidates.sort(key=lambda c: c[2], reverse=True)
    return candidates
