"""MMR / diversity panel -- ARCHITECTURE.md §8.D:

    MMR lambda ~= 0.7 * max 1 per org * max 2 per area * max 2 per format
    * max 1 paid per rail

Nothing in this repo implements MMR or any post-filter diversity pass
yet (grepped: no `mmr`/`diversity` hits outside this package and
`now_search.rrf`'s own doc-comment mentioning it as a *future* step).
It depends on `org` (from E1.5 partner-roster clustering, not joined to
articles anywhere yet), `area` (from E2.3/E2.5 place/geocode linkage)
and `format` (E2.1, NULL today) -- none of which this candidate set can
resolve for an article-only query.

Rendered as an honest stub per the ticket's design note ("if a panel
cannot be populated yet, render the honest empty state rather than
omitting the panel") -- never a silently empty table that could be
mistaken for "nothing was demoted".
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DiversityStub:
    implemented: bool
    note: str
    needs: list[str]


def stub() -> DiversityStub:
    return DiversityStub(
        implemented=False,
        note="MMR / diversity is not implemented anywhere in this codebase yet. §8.D's rule "
        "(lambda~=0.7, max 1/org, max 2/area, max 2/format, max 1 paid/rail) has no code to call.",
        needs=[
            "org linkage per article (E1.5 clusters domains into orgs, but articles are not yet "
            "joined to org_id anywhere queryable)",
            "area (E2.3 place extraction + E2.5 geocoding, both in progress this wave)",
            "format (E2.1 classifier, not started -- format is NULL on all 4,772 rows)",
            "an actual MMR pass over the top-~40 candidates (E3.3's blender scope, ARCHITECTURE.md "
            "§7's online pipeline diagram)",
        ],
    )
