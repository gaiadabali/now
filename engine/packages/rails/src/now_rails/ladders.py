"""Rail-specific fallback-ladder rung sequences (ARCHITECTURE.md Sec.8.F),
built from `now_filters.models.RungSpec` so every rail's rung tracking and
`now_filters.ladder.run_ladder`'s defensive competitor/status re-check are
identical machinery, not three reimplementations of the same idea.

`RungSpec` was designed around Row 2's geo dimensions (`radius_m`,
`require_open_now`) -- Row 1 and Row 3 have no radius or open-now concept,
so their ladders below only vary the fields that mean something for them
(`area_level`, `editorial_fallback`) and simply leave the geo-only fields
at their dataclass defaults; each rail's own `fetch_fn` (in
`row1_complementary.py`/`row3_similar.py`) reads only the fields it needs
from the `RungSpec` it's handed, exactly as `run_ladder`'s own docstring
describes a caller-owned `FetchFn` doing.

Row 3's `editorial_fallback` flag is deliberately repurposed as a plain
"drop the quality floor" toggle (there is no places-style curated/popular
list of *articles* to fall back to, and no `RungSpec` field named for
that) -- documented here, once, rather than left to be inferred from
`row3_similar.py`'s `fetch_fn` alone.
"""

from __future__ import annotations

from now_filters.models import RungSpec

ROW1_LADDER: tuple[RungSpec, ...] = (
    RungSpec(name="strict", area_level="area"),
    RungSpec(name="area_to_district", area_level="district"),
    RungSpec(name="district_to_city", area_level="city"),
    RungSpec(name="editorial_fallback", area_level="city", editorial_fallback=True),
)

ROW3_LADDER: tuple[RungSpec, ...] = (
    RungSpec(name="strict"),
    RungSpec(name="drop_quality_floor", editorial_fallback=True),
)

LADDER_FILL_MULTIPLIER = 3  # see ladder_target()'s docstring


def ladder_target(k: int, rerank_pool: int) -> int:
    """`now_filters.ladder.run_ladder`'s `slots_needed` drives BOTH the
    stopping condition for rung escalation and the final truncation --
    passing the full `rerank_pool` (~40, ARCHITECTURE.md Sec.7's "re-rank
    ... top ~40") as `slots_needed` means a rail escalates to its very
    worst rung whenever fewer than 40 genuine candidates exist anywhere,
    which is the common case for Row 1/2's place pools (a real venue's
    complements or nearby set is routinely single digits to a few dozen,
    not 40+) -- `now_filters`' own reference usage
    (`tests/test_ladder_competitor_survives_all_rungs.py`,
    `now_filters.cli`) passes small, display-sized `slots_needed` values
    (5-10), not a 40-wide rerank pool, for exactly this reason.

    This is the disclosed middle ground: enough headroom above `k` for
    MMR diversity/caps to have real choices to make, without demanding
    the full aspirational rerank-pool width the ladder's escalation would
    rarely satisfy against a realistic (or synthetic-test-sized) venue
    count. Capped at `rerank_pool` so a large `k` never asks for more than
    the rerank pool itself.
    """
    return min(rerank_pool, max(k * LADDER_FILL_MULTIPLIER, k))
