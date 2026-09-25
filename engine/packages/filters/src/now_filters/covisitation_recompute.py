"""Recomputes `engine.covisitation` (migration 0001, entity columns widened
to `text` by migration 0005) from real `engine.interactions` -- the write
side `now_blender.covisitation` has always been missing (see that module's
own docstring: "genuinely wired -- and genuinely empty"). WS1, Edition 2,
fourth pass, item 4: "Ensure the worker's covisitation job runs on a
schedule and writes `engine.covisitation` from real interactions."

## The pair, and what counts as a qualifying view

Two articles "co-visit" when the same session (`engine.interactions
.session_id`) produced a QUALIFYING interaction with both, within the
recompute window (`window_days`, default 30 -- matching
`now_blender.covisitation.DEFAULT_WINDOW = "30d"`, the value the read side
already asks for). Qualifying uses the SAME rule
`apps/web/src/lib/recommend.ts#INTERACTION_WEIGHT` applies for taste
centroids: `click`, or `dwell` >= 30s, or `scroll` >= 70% -- a bare
`view`/`impression` is not "this reader engaged with it", and folding those
in would covisit every pair of articles that ever appeared on the same
page load.

## The score, and why it is directional

`score(a, b) = sessions_with_both(a, b) / sessions_with(a)` -- "of the
sessions that engaged with A, what fraction also engaged with B." This is
NOT symmetric (`score(a, b) != score(b, a)` in general: a niche article
b's readers may overwhelmingly also read a popular a, while a's much
larger audience only rarely also reaches b), which matches how the read
side queries it: `fetch_covis_scores(subject_entity_id=a, ...)` asks
specifically "what does A's audience also read", the same framing this
module computes FROM.

## min_support

A pair with a single shared session is one coincidence, not a pattern --
`min_support` (default 2) requires at least that many DISTINCT sessions
before a pair counts at all, independent of the READ-side floor
(`lib/recommendSql.ts`'s `MIN_COVIS_SCORE`) applied again at query time as
a belt-and-suspenders check against a future writer with a looser floor.

## Diff-aware, same shape as `hidden_rival_recompute`

Full recompute each run (this table is bounded by co-occurring PUBLISHED
article pairs within a rolling window, not unbounded), diffed against what
is already there FOR THAT WINDOW LABEL so a stale pair from a shrinking
audience is actually removed, not just never-updated. Reports
added/removed/unchanged like `hidden_rival_recompute.RecomputeReport` so
the same "a non-zero diff on a quiet night is worth a look" logging
convention applies in `app/jobs.py`.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.engine import Connection

DEFAULT_WINDOW_DAYS = 30
DEFAULT_WINDOW_LABEL = "30d"  # matches now_blender.covisitation.DEFAULT_WINDOW
DEFAULT_MIN_SUPPORT = 2
DEFAULT_COVISITATION_TABLE = "engine.covisitation"
DEFAULT_INTERACTIONS_TABLE = "engine.interactions"

# Same qualifying-signal rule as apps/web/src/lib/recommend.ts's
# INTERACTION_WEIGHT / fetchWeightedTasteInputs -- duplicated here because
# this is a separate process with no shared module between TS and Python
# for it (same reasoning lib/recommendSql.ts gives for its own duplicated
# TYPE_TO_SECTION map).
_QUALIFYING_SESSIONS_SQL_TEMPLATE = """
    SELECT DISTINCT session_id, entity_id::text AS entity_id
      FROM {interactions_table}
     WHERE entity_type = 'article'
       AND ts >= now() - (:window_days || ' days')::interval
       AND (
             kind = 'click'
          OR (kind = 'dwell' AND COALESCE(dwell_ms, 0) >= 30000)
          OR (kind = 'scroll' AND COALESCE(scroll_pct, 0) >= 70)
       )
"""

_PAIR_COUNTS_SQL_TEMPLATE = """
    WITH qualifying AS ({qualifying_sql}),
    totals AS (
        SELECT entity_id, count(DISTINCT session_id) AS session_count
          FROM qualifying
         GROUP BY entity_id
    ),
    pairs AS (
        SELECT a.entity_id AS entity_a, b.entity_id AS entity_b,
               count(DISTINCT a.session_id) AS co_count
          FROM qualifying a
          JOIN qualifying b ON a.session_id = b.session_id AND a.entity_id <> b.entity_id
         GROUP BY a.entity_id, b.entity_id
        HAVING count(DISTINCT a.session_id) >= :min_support
    )
    SELECT p.entity_a, p.entity_b, p.co_count, t.session_count
      FROM pairs p
      JOIN totals t ON t.entity_id = p.entity_a
"""


@dataclass(frozen=True)
class CovisitationRecomputeReport:
    pairs_considered: int
    added: int
    removed: int
    unchanged: int

    @property
    def changed(self) -> bool:
        return self.added > 0 or self.removed > 0


def recompute_covisitation(
    conn: Connection,
    *,
    window_days: int = DEFAULT_WINDOW_DAYS,
    window_label: str = DEFAULT_WINDOW_LABEL,
    min_support: int = DEFAULT_MIN_SUPPORT,
    covisitation_table: str = DEFAULT_COVISITATION_TABLE,
    interactions_table: str = DEFAULT_INTERACTIONS_TABLE,
) -> CovisitationRecomputeReport:
    """Full recompute for one `window_label`, diffed against what is
    already there for that label so a pair that no longer clears
    `min_support` is actually removed rather than left to go stale
    forever. Idempotent: running it twice in a row with no new
    interactions produces `added=0, removed=0`.

    `covisitation_table`/`interactions_table` are parameterized (same
    reasoning `hidden_rival_recompute.py` gives its own table-name
    parameters): tests point them at `now_filters.synthetic`'s temp
    tables, production leaves the defaults."""

    pair_counts_sql = _PAIR_COUNTS_SQL_TEMPLATE.format(
        qualifying_sql=_QUALIFYING_SESSIONS_SQL_TEMPLATE.format(interactions_table=interactions_table)
    )
    rows = conn.execute(
        text(pair_counts_sql), {"window_days": window_days, "min_support": min_support}
    ).fetchall()

    new_scores: dict[tuple[str, str], float] = {}
    for entity_a, entity_b, co_count, session_count in rows:
        if session_count <= 0:
            continue
        new_scores[(entity_a, entity_b)] = float(co_count) / float(session_count)

    existing_rows = conn.execute(
        text(f'SELECT entity_a, entity_b, score FROM {covisitation_table} WHERE "window" = :window'),
        {"window": window_label},
    ).fetchall()
    existing_scores: dict[tuple[str, str], float] = {(a, b): float(s) for a, b, s in existing_rows}

    new_keys = set(new_scores.keys())
    existing_keys = set(existing_scores.keys())

    # "Changed" here means added, removed, OR the score moved -- a pair
    # that still exists but whose score drifted needs the UPSERT too, or a
    # nightly recompute with stable membership but shifting audience
    # composition would silently freeze at its first-ever score forever.
    added = new_keys - existing_keys
    removed = existing_keys - new_keys
    unchanged = {k for k in (new_keys & existing_keys) if new_scores[k] == existing_scores[k]}
    to_upsert = (new_keys - unchanged)

    for entity_a, entity_b in removed:
        conn.execute(
            text(
                f'DELETE FROM {covisitation_table} '
                f'WHERE entity_a = :entity_a AND entity_b = :entity_b AND "window" = :window'
            ),
            {"entity_a": entity_a, "entity_b": entity_b, "window": window_label},
        )

    for entity_a, entity_b in to_upsert:
        conn.execute(
            text(
                f"""
                INSERT INTO {covisitation_table} (entity_a, entity_b, score, "window", computed_at)
                VALUES (:entity_a, :entity_b, :score, :window, now())
                ON CONFLICT (entity_a, entity_b, "window")
                DO UPDATE SET score = EXCLUDED.score, computed_at = EXCLUDED.computed_at
                """
            ),
            {
                "entity_a": entity_a,
                "entity_b": entity_b,
                "score": new_scores[(entity_a, entity_b)],
                "window": window_label,
            },
        )

    return CovisitationRecomputeReport(
        pairs_considered=len(new_scores),
        added=len(added),
        removed=len(removed),
        unchanged=len(unchanged),
    )
