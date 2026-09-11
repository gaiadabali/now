"""Reads `engine.covisitation` for the blend's `w_cf` term.

Real table, real query, genuinely wired -- **and genuinely empty**:
`SELECT count(*) FROM engine.covisitation` returns 0 on `now_jakarta`
today (verified directly). ARCHITECTURE.md's own roadmap (Sec.10 "ML
roadmap") gates this table's population behind E7.3 ("~50k sessions"),
which itself is gated behind the beacon actually being deployed
(PROGRESS.md: "beacon not deployed yet"). So `covis_score` is `None` for
every candidate on every real query today -- not a bug, not a stub
function that always returns `None` without asking the database; this
module asks, gets zero rows, and reports the honest result. The day
E7.3 populates the table, this module needs no change to start
returning real scores.

Covisitation is inherently pairwise against a **subject** entity ("what
gets co-visited with THIS one") -- there is no subject in a plain
keyword search (Row 1 Complementary, E3.5, is where a subject exists).
`fetch_covis_scores` therefore takes an optional `subject_entity_id`;
when it is `None` (the search-rerank path this package's `reranker.py`
exercises today), it returns an empty dict without querying, which is
the same `None`-per-candidate outcome as an empty result set would give,
without paying for a query that cannot possibly match anything.
"""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.engine import Connection

DEFAULT_WINDOW = "30d"

_SELECT_SQL = text(
    """
    SELECT entity_b, score
      FROM engine.covisitation
     WHERE entity_a = :subject AND window = :window AND entity_b = ANY(:candidates)
    """
)


def fetch_covis_scores(
    conn: Connection,
    *,
    subject_entity_id: str | None,
    candidate_entity_ids: list[str],
    window: str = DEFAULT_WINDOW,
) -> dict[str, float]:
    if subject_entity_id is None or not candidate_entity_ids:
        return {}
    rows = conn.execute(
        _SELECT_SQL, {"subject": subject_entity_id, "window": window, "candidates": candidate_entity_ids}
    ).fetchall()
    return {entity_b: float(score) for entity_b, score in rows}
