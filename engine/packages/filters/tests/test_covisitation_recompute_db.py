"""DB-integration coverage for `now_filters.covisitation_recompute` --
WS1, Edition 2, fourth pass, item 6 ("unit tests for ... the covisitation
floor"). Skips cleanly if `now_jakarta` is unreachable (this package's own
`conftest.py` convention, see `test_hidden_rival_recompute_db.py` for the
identical pattern this file follows).

Synthetic `now_filters_synth_interactions`/`now_filters_synth_covisitation`
temp tables throughout -- never the real `engine.interactions`/
`engine.covisitation`.
"""

from __future__ import annotations

from sqlalchemy import text

from now_filters.covisitation_recompute import recompute_covisitation
from now_filters.synthetic import (
    SYNTH_COVISITATION_TABLE,
    SYNTH_INTERACTIONS_TABLE,
    SyntheticInteraction,
    create_synthetic_covisitation_table,
    create_synthetic_interactions_table,
)

_KWARGS = dict(covisitation_table=SYNTH_COVISITATION_TABLE, interactions_table=SYNTH_INTERACTIONS_TABLE)


def _covis_rows(conn) -> set[tuple[str, str]]:
    rows = conn.execute(text(f'SELECT entity_a, entity_b FROM {SYNTH_COVISITATION_TABLE}')).fetchall()
    return {(r.entity_a, r.entity_b) for r in rows}


def test_two_sessions_reading_the_same_pair_produce_a_directional_score(conn):
    # Two sessions both read article 1 then article 2 (qualifying clicks);
    # a third session reads only article 1. score(1 -> 2) = 2/3 (2 of the
    # 3 sessions that engaged with 1 also engaged with 2); score(2 -> 1) =
    # 2/2 = 1.0 (both sessions that engaged with 2 also engaged with 1) --
    # the asymmetry the module's docstring describes.
    rows = [
        SyntheticInteraction(session_id="00000000-0000-0000-0000-000000000001", entity_id=1, kind="click"),
        SyntheticInteraction(session_id="00000000-0000-0000-0000-000000000001", entity_id=2, kind="click"),
        SyntheticInteraction(session_id="00000000-0000-0000-0000-000000000002", entity_id=1, kind="click"),
        SyntheticInteraction(session_id="00000000-0000-0000-0000-000000000002", entity_id=2, kind="click"),
        SyntheticInteraction(session_id="00000000-0000-0000-0000-000000000003", entity_id=1, kind="click"),
    ]
    create_synthetic_interactions_table(conn, rows)
    create_synthetic_covisitation_table(conn)

    report = recompute_covisitation(conn, min_support=2, **_KWARGS)
    assert report.added == 2  # (1,2) and (2,1)
    assert report.pairs_considered == 2

    scores = {
        (r.entity_a, r.entity_b): float(r.score)
        for r in conn.execute(text(f"SELECT entity_a, entity_b, score FROM {SYNTH_COVISITATION_TABLE}"))
    }
    # `numeric(8,5)` rounds in storage, so the comparison tolerance must be
    # looser than the write precision, not tighter.
    assert abs(scores[("1", "2")] - (2 / 3)) < 1e-4
    assert abs(scores[("2", "1")] - 1.0) < 1e-4


def test_min_support_excludes_a_single_shared_session(conn):
    rows = [
        SyntheticInteraction(session_id="00000000-0000-0000-0000-000000000001", entity_id=10, kind="click"),
        SyntheticInteraction(session_id="00000000-0000-0000-0000-000000000001", entity_id=20, kind="click"),
    ]
    create_synthetic_interactions_table(conn, rows)
    create_synthetic_covisitation_table(conn)

    report = recompute_covisitation(conn, min_support=2, **_KWARGS)
    assert report.pairs_considered == 0
    assert _covis_rows(conn) == set()


def test_unqualified_dwell_and_scroll_do_not_count(conn):
    rows = [
        SyntheticInteraction(session_id="00000000-0000-0000-0000-000000000001", entity_id=1, kind="dwell", dwell_ms=5_000),
        SyntheticInteraction(session_id="00000000-0000-0000-0000-000000000001", entity_id=2, kind="scroll", scroll_pct=10),
        SyntheticInteraction(session_id="00000000-0000-0000-0000-000000000002", entity_id=1, kind="dwell", dwell_ms=45_000),
        SyntheticInteraction(session_id="00000000-0000-0000-0000-000000000002", entity_id=2, kind="scroll", scroll_pct=90),
    ]
    create_synthetic_interactions_table(conn, rows)
    create_synthetic_covisitation_table(conn)

    report = recompute_covisitation(conn, min_support=1, **_KWARGS)
    # Only session 2's dwell (>=30s) and scroll (>=70%) qualify -- session
    # 1's shallow dwell/scroll must not contribute a co-visit.
    assert report.pairs_considered == 2
    assert ("1", "2") in _covis_rows(conn)


def test_second_run_with_no_new_interactions_is_a_no_op(conn):
    rows = [
        SyntheticInteraction(session_id="00000000-0000-0000-0000-000000000001", entity_id=1, kind="click"),
        SyntheticInteraction(session_id="00000000-0000-0000-0000-000000000001", entity_id=2, kind="click"),
        SyntheticInteraction(session_id="00000000-0000-0000-0000-000000000002", entity_id=1, kind="click"),
        SyntheticInteraction(session_id="00000000-0000-0000-0000-000000000002", entity_id=2, kind="click"),
    ]
    create_synthetic_interactions_table(conn, rows)
    create_synthetic_covisitation_table(conn)

    first = recompute_covisitation(conn, min_support=2, **_KWARGS)
    assert first.changed is True

    second = recompute_covisitation(conn, min_support=2, **_KWARGS)
    assert second.added == 0
    assert second.removed == 0
    assert second.changed is False


def test_a_pair_that_drops_below_min_support_is_removed_on_recompute(conn):
    # First recompute with these interactions and a low floor establishes
    # the pair; a second recompute against an EMPTY interactions table
    # (as if the window rolled past every qualifying event) must remove
    # the now-stale row rather than leave it forever.
    rows = [
        SyntheticInteraction(session_id="00000000-0000-0000-0000-000000000001", entity_id=1, kind="click"),
        SyntheticInteraction(session_id="00000000-0000-0000-0000-000000000001", entity_id=2, kind="click"),
    ]
    create_synthetic_interactions_table(conn, rows)
    create_synthetic_covisitation_table(conn)
    first = recompute_covisitation(conn, min_support=1, **_KWARGS)
    assert first.pairs_considered == 2

    create_synthetic_interactions_table(conn, [])  # window rolled past everything
    second = recompute_covisitation(conn, min_support=1, **_KWARGS)
    assert second.removed == 2
    assert _covis_rows(conn) == set()
