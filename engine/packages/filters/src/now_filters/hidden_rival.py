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



# Measured 2026-09-24 against real `place_mentions`/`places` data in both
# cities (this ticket's hand-labelled sample, ~250 `role='featured'` rows
# read by the implementing engineer -- see the ticket report for the full
# methodology and counts): the bare word "club" is `nightclub`'s own
# taxonomy alias, correct for the E2.1 classifier prompt this file also
# serves, but as a NAME-MATCH keyword for this guard it is dominated by
# false positives -- "The American Club Jakarta", "Polish Business Club",
# "Royale Jakarta Golf Club", "Club Med", "Trump International Golf Club",
# "Cork & Screw Country Club", "Women's International Club" are all social,
# sports or expat-association clubs, not F&B venues, and outnumbered the
# genuine drink-venue matches (real beach clubs/nightclubs) by roughly 3
# to 1 in the sample. Every one of those false positives disappears once
# "club" alone is dropped, because the genuine venues in the same sample
# ("Potato Head Beach Club", "Sundays Beach Club", "BUNK Lobby Lounge",
# "Emilia Bar Italiano") still match via the more specific phrases
# ("beach club", "lounge", "bar") that stay in the lexicon. The
# recall cost is real but small and measured (five Bali articles in the
# sample -- "Mama San Supper Club", "Kuta Social Club" x2, "The Jungle Club
# Ubud", "KANVA Ubud by K Club" -- were caught ONLY via bare "club" and are
# no longer flagged) and is the right side to err on for a guard whose
# failure mode must be "misses a rival" rather than "wrongly empties a
# rail" (deliverable #2's own constraint).
#
# This denylist is scoped to THIS module's guard use only -- it does not
# edit `type.json` itself, so the classifier prompt and human review this
# file also serves keep "club" as a legitimate nightclub cue.
_GUARD_AMBIGUOUS_KEYWORDS: dict[str, frozenset[str]] = {
    "drink": frozenset({"club"}),
}


def load_subtype_lexicon(seed_dir: Path | str | None = None) -> dict[str, tuple[str, ...]]:
    """L1 `type` slug -> the subtype `label`s and `aliases` filed under it,
    lowercased, exactly as authored in `type.json`, minus
    `_GUARD_AMBIGUOUS_KEYWORDS` -- every remaining entry is a human-written
    taxonomy word (`Resort`, `Beach club`, `warung`), never a proper noun --
    see module docstring."""
    import json

    doc = json.loads(_type_json_path(seed_dir).read_text(encoding="utf-8"))
    lexicon: dict[str, tuple[str, ...]] = {}
    for l1 in doc["terms"]:
        keywords: set[str] = set()
        for child in l1.get("children", []):
            label = child.get("label")
            if label:
                keywords.add(str(label).strip().lower())
            for alias in child.get("aliases") or []:
                keywords.add(str(alias).strip().lower())
        keywords -= _GUARD_AMBIGUOUS_KEYWORDS.get(l1["slug"], frozenset())
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
