"""The hidden-rival guard (Edition 2, 2026-09-24, docs/EDITION-2-PLAN.md
deliverable #2) -- a candidate filed under one L1 `type` whose article is
really centrally about a competing venue. The case that named it: on the
Bali Kimpton (`stay`) story, Read Next offered article 4417, "The Westin
Resort Nusa Dua, Bali Presents Celebrate Wellness 2026" -- typed `event`
(source `ai`, confidence 0.84). `excluded_types_for`/`is_competitor`
(`type_relations.py`) can only ever see the DECLARED type, so a mistyped
or narrowly-typed article (a hotel's wellness event, filed as `event`) is
invisible to them by construction. This module is the second, independent
check: not "what type does the classifier say this is", but "what venue
does this article's own place_mentions say it is centrally about".

## Why a taxonomy-label lexicon, not a brand-name list

The task is explicit that no brand name may be hardcoded in code. The
signal used here is narrower and more durable than a brand roster: every
subtype term in the `type` facet already carries a human `label` and, for
many, a list of `aliases` (`engine/packages/taxonomy/seed/terms/type.json`
-- "documentation for the E2.1 classifier prompt and the human review",
per that file's own `note`). "The Westin Resort **Nusa Dua**" matches
because it contains the word "Resort", one of `stay`'s own subtype labels
-- not because "Westin" is listed anywhere. This generalises to any hotel,
restaurant or bar chain the roster has never seen, in either city, and it
is the same file the classifier prompt and the taxonomy review already
depend on -- reusing it here does not introduce a second vocabulary to
keep in sync.

## Why place_mentions, and why `role='featured'` only

`place_mentions.role` is the CMS's own ordering of how central a place is
to a piece (`subject.py`'s `_ROLE_PRIORITY_SQL` already ranks
featured > reviewed > mentioned for the identical reason). A candidate
that merely name-drops a hotel in passing (`role='mentioned'`, 9,893 of
11,316 rows measured 2026-09-24) is not "an article about that hotel" --
only `featured` (1,423 rows) is used here. This is deliberately narrower
than `subject.py`'s own featured > reviewed cascade: `reviewed` is "this
piece is a considered review of X", which is much more likely to ALSO
carry an honest declared type, whereas `featured` (used for anything from
a full review to an event write-up centred on a venue) is exactly the
looser, riskier case F50/the Westin example both are.

**Honest limit, measured 2026-09-24 against the real article (id 4417):**
`role='featured'`-only does NOT catch this exact article. Its single
`featured` mention is the EVENT'S own name ("Celebrate Wellness 2026"),
which does not match any venue lexicon; the hotel name ("The Westin
Resort Nusa Dua") appears twice, both `role='mentioned'`, and worse, as
TWO DIFFERENT `place_id` rows (12522, and 15504 "Director of Wellness at
The Westin Resort Nusa Dua" -- an entity-extraction fragment, not a
second real venue) -- so neither `role='featured'` nor a same-`place_id`
recurrence count reaches this one case. This is an upstream
entity-resolution gap (the loader created two unlinked place rows for one
venue), not something a name-matching guard can close. A follow-up
measured on real data (both cities, `primary_type='event'` candidates,
`role='mentioned'` mentions whose PLACE recurs >=2 times for the same
`place_id`): 8 of 11 flagged were genuine venue-in-an-event-writeup cases
structurally identical to the Westin pattern (a hotel/resort hosting the
event) -- worth adding once entity resolution can link fragmented mentions
of the same real-world venue, tracked as a follow-up rather than shipped
here with only 11 real examples to validate it against.

The `role='featured'` rule this module DOES ship is validated on a much
larger, hand-reviewed sample -- see the ticket report for the full
precision measurement (~250+ rows, both cities, ~86% measured precision
on the four venue-competitor categories after the `club` curation below,
higher on `wellness`).

## Second signal (second pass, same date): the candidate's own TITLE

Article 4417 is not caught by the mention-based rule above (its title
contains "The Westin Resort Nusa Dua, Bali Presents Celebrate Wellness
2026" -- the word "Resort" is right there). `title_signal_enabled_types`
gates a second, independent check: for a candidate whose own declared
`primary_type` is NOT a venue type (`exclude_same=false`: `event`/
`editorial`/`do`, or NULL), does its TITLE itself match a subtype keyword
of a type the subject excludes? Measured (ticket report, ~440 hand-
reviewed real titles, both cities): `stay` clears ~85-94% precision,
driven by specific hotel/resort brand names in promotional titles --
enabled below. `eat`/`shop`/`wellness` measured 37-71%, dominated by this
magazine's own recurring awards/association franchise and generic abstract
nouns ("beauty", "craft", "market") in editorial writing that name no
specific venue -- NOT enabled, with the exact noise and a proposed
curated override recorded in `hidden_rival_lexicon_overrides.json` rather
than silently widened or narrowed. `drink` measured borderline (~84%,
small/noisy sample) and is also not enabled yet.

**Precomputed, not live** (second pass): both signals above write into
`engine.hidden_rival_flags` (migration 0009) via
`now_filters.hidden_rival_recompute`, offline. `EXPLAIN (ANALYZE,
BUFFERS)` against real data showed the live regex join costing ~40ms of a
150ms total-page budget, repeated on every request across up to five rail
queries, for a signal that only changes when an article is edited or a
place is renamed (ARCHITECTURE.md principle 2: `engine` is derived and
rebuildable). The functions in this module (`build_name_pattern`,
`hidden_rival_pattern_for_subject`) are now the RECOMPUTE script's tools,
not a live per-request code path; `now_filters.hard`'s hidden-rival
predicate reads the precomputed table instead.

## Why this does not need `orgs`/`places.type`

`places.type` is unusable for this signal today -- every place in both
cities still wears the F27/F49 loader sentinel (`editorial`/
`pending_review`) pending E2.x place classification, and `orgs.type` is
empty archive-wide (only the unreviewed `orgs.type_guess` is populated,
for 217 of 1,562 orgs, and `places.org_id` is not populated for the
mentions this guard cares about -- verified directly against
`now_bali`/`now_jakarta` 2026-09-24). The place's own NAME, matched
against the taxonomy's subtype vocabulary, is the one signal actually
populated for every place today.
"""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

from now_db.provisioning import TAXONOMY_SEED_DIR

DEFAULT_PLACE_MENTIONS_TABLE = "public.place_mentions"

# The CMS's own strongest "this piece is centrally about this place" signal
# -- see module docstring for why `reviewed`/`mentioned` are excluded.
HIDDEN_RIVAL_ROLE = "featured"


def _type_json_path(seed_dir: Path | str | None = None) -> Path:
    root = Path(seed_dir) if seed_dir is not None else TAXONOMY_SEED_DIR
    return root / "terms" / "type.json"


def _overrides_json_path(seed_dir: Path | str | None = None) -> Path:
    root = Path(seed_dir) if seed_dir is not None else TAXONOMY_SEED_DIR
    return root / "hidden_rival_lexicon_overrides.json"


def _load_guard_ambiguous_keywords(seed_dir: Path | str | None = None) -> dict[str, frozenset[str]]:
    """Reads `hidden_rival_lexicon_overrides.json` -- the measured,
    documented denylist ("club" for `drink`, see that file) shared with
    `engine/apps/web/src/lib/hiddenRival.ts`'s TypeScript port, so neither
    language's copy of the curation can drift from the other's. A missing
    file (an older checkout, or a seed_dir built for a test that has no
    reason to define one) means "no overrides", not an error -- this
    curation is a precision improvement on top of the base lexicon, never
    something the guard depends on to function at all."""
    import json

    path = _overrides_json_path(seed_dir)
    if not path.is_file():
        return {}
    doc = json.loads(path.read_text(encoding="utf-8"))
    return {
        type_slug: frozenset(str(w).strip().lower() for w in entry.get("words", []))
        for type_slug, entry in doc.get("excluded_by_type", {}).items()
    }


def title_signal_enabled_types(seed_dir: Path | str | None = None) -> frozenset[str]:
    """L1 types the TITLE signal is enabled for -- see module docstring's
    "Second signal" section. Data-driven: adding a type here (once its
    precision is measured and documented) is the whole enable switch, no
    code change. Missing file / missing key -> empty (nothing enabled),
    the same fail-safe-by-omission stance `_load_guard_ambiguous_keywords`
    takes for its own key."""
    import json

    path = _overrides_json_path(seed_dir)
    if not path.is_file():
        return frozenset()
    doc = json.loads(path.read_text(encoding="utf-8"))
    return frozenset(doc.get("title_signal_enabled_types", {}).keys())


def load_subtype_lexicon(seed_dir: Path | str | None = None) -> dict[str, tuple[str, ...]]:
    """L1 `type` slug -> the subtype `label`s and `aliases` filed under it,
    lowercased, exactly as authored in `type.json`, minus this guard's
    measured curation (`hidden_rival_lexicon_overrides.json`) -- every
    remaining entry is a human-written taxonomy word (`Resort`, `Beach
    club`, `warung`), never a proper noun -- see module docstring."""
    import json

    doc = json.loads(_type_json_path(seed_dir).read_text(encoding="utf-8"))
    overrides = _load_guard_ambiguous_keywords(seed_dir)
    lexicon: dict[str, tuple[str, ...]] = {}
    for l1 in doc["terms"]:
        keywords: set[str] = set()
        for child in l1.get("children", []):
            label = child.get("label")
            if label:
                keywords.add(str(label).strip().lower())
            for alias in child.get("aliases") or []:
                keywords.add(str(alias).strip().lower())
        keywords -= overrides.get(l1["slug"], frozenset())
        lexicon[l1["slug"]] = tuple(sorted(keywords))
    return lexicon


@lru_cache(maxsize=1)
def _cached_default_lexicon() -> dict[str, tuple[str, ...]]:
    # Module-level cache: `type.json` is a ~700-line static file read from
    # disk, not per-request data -- re-parsing it on every rail request
    # would be pure waste on the p95 path this ticket has a 150ms budget
    # for. Callers that need a non-default seed dir (tests) pass
    # `seed_dir=...` to `load_subtype_lexicon` directly and bypass the cache.
    return load_subtype_lexicon()


def default_lexicon() -> dict[str, tuple[str, ...]]:
    return _cached_default_lexicon()


def _escape_keyword(keyword: str) -> str:
    """POSIX ARE (Postgres's `~*`) doesn't understand Python's `re.escape`
    output one-for-one, but every metacharacter it needs escaped here is
    also special in POSIX ARE, and none of these keywords contain a
    backslash -- so `re.escape` is safe to reuse rather than hand-rolling a
    second escaper for one dialect difference the data never exercises."""
    return re.escape(keyword)


def build_name_pattern(types: frozenset[str] | set[str], lexicon: dict[str, tuple[str, ...]] | None = None) -> str | None:
    """A single POSIX ARE alternation matching any subtype keyword filed
    under any of `types`, word-bounded (`\\y`) so "bar" matches "Sky Garden
    **Bar**" and not "**Bar**bershop". Returns `None` if `types` contributes
    no keywords at all (e.g. only `unknown`, which has no subtypes) --
    callers must treat `None` as "nothing to match", not "match everything".
    """
    lex = lexicon or default_lexicon()
    keywords: set[str] = set()
    for t in types:
        keywords.update(lex.get(t, ()))
    if not keywords:
        return None
    alternation = "|".join(_escape_keyword(k) for k in sorted(keywords))
    return rf"\y({alternation})\y"


def hidden_rival_pattern_for_subject(
    subject_type: str | None,
    relations: dict,
    *,
    lexicon: dict[str, tuple[str, ...]] | None = None,
) -> str | None:
    """The pattern for THIS subject's guard: every keyword belonging to any
    type `excluded_types_for(subject_type)` already names (§4's matrix,
    `competes_with` included) -- `unknown` contributes nothing (no
    subtypes), which is correct: the guard's job is to catch a candidate
    hiding a REAL venue type, not to guess at the unclassified sentinel.
    """
    from now_filters.type_relations import excluded_types_for

    excluded = excluded_types_for(relations, subject_type) - {"unknown"}
    if not excluded:
        return None
    return build_name_pattern(excluded, lexicon=lexicon)
