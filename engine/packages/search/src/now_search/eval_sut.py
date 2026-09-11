"""Wires `SearchEngine` into `now_eval`'s `SystemUnderTest` Protocol so
`now-eval`'s harness (`evaluate_search`, `metrics.ndcg`) can score this
package's hybrid search against the E2.7 provisional query set and
report nDCG@10 vs. the recorded trivial-random baseline
(engine/packages/eval/data/baseline.json, nDCG@10 = 0.0060).

**Scope note**: the task brief scopes an eval SUT adapter to
`engine/packages/eval/src/now_eval/sut/**` *if it does not modify
existing eval files*. That path cannot actually be used without
modifying existing eval behaviour: `now_eval/sut.py` already exists as
a plain module (not a package), and every existing importer does
`from .sut import SystemUnderTest` etc. Creating a *package* directory
`now_eval/sut/` alongside it does not coexist with that module --
verified directly: Python's import system resolves the package
directory and the sibling `sut.py` module becomes completely
unreachable (`import pkg.sut` returns the package, `sut.py`'s contents
are never loaded). That would silently break `harness.py`,
`baseline.py`'s CLI, and every existing eval test that imports
`now_eval.sut` -- exactly the "modify existing eval files" this task is
scoped to avoid, just achieved by adding a file instead of editing one.

So this adapter lives here instead, in the package this task *does*
own, and is wired in by calling `now_eval`'s public, unmodified
`evaluate_search()` function directly (see `now_search/cli.py`'s `eval`
command) -- exactly the extension path `now_eval/sut.py`'s own
docstring describes: "the day a real classifier or search ranker
exists, it is wired in by implementing this interface -- no harness
code changes." No file under `engine/packages/eval/` is created,
edited, or imported-in-a-way-that-shadows anything.

Article-id format bridge: `now_eval`'s labelled sets key everything by
`f"wp:{wp_id}"` (`now_eval.datasets.sources.Article.article_id`) --
WordPress's legacy numeric id. This package's DB layer keys everything
by `public.articles.id` (Payload's PK). `public.articles.legacy_wp_id`
is the bridge (verified: unique, populated on all 4,772 published rows).
`WpIdBridge` below loads that mapping once per process.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.engine import Connection

from now_search.engine import SearchEngine

_WP_ID_MAP_SQL = text(
    "SELECT id, legacy_wp_id FROM public.articles WHERE legacy_wp_id IS NOT NULL"
)

# Requesting more than `k` from the underlying engine before mapping back
# to wp:-space and intersecting with the eval harness's candidate set --
# in this harness candidate_ids is always the *entire* corpus (see
# now_eval.harness.evaluate_search: `sut.rank(q.query, list(all_article_ids), k)`),
# so in practice every mapped hit survives the intersection and this is a
# no-op safety margin, not something load-bearing today.
OVERFETCH_MULTIPLIER = 5


@dataclass
class WpIdBridge:
    wp_to_db: dict[int, int]
    db_to_wp: dict[int, int]

    @classmethod
    def load(cls, conn: Connection) -> "WpIdBridge":
        rows = conn.execute(_WP_ID_MAP_SQL).fetchall()
        wp_to_db: dict[int, int] = {}
        db_to_wp: dict[int, int] = {}
        for db_id, legacy_wp_id in rows:
            wp_id = int(legacy_wp_id)
            wp_to_db[wp_id] = db_id
            db_to_wp[db_id] = wp_id
        return cls(wp_to_db=wp_to_db, db_to_wp=db_to_wp)


class SearchEvalSUT:
    """Duck-types `now_eval.sut.SystemUnderTest` for the `search` surface
    only. `related`/`tag_facets`/`classify_type` are out of this
    ticket's scope (E3.5-3.7, E2.1, E2.2 respectively) and raise
    NotImplementedError rather than silently returning a fake answer --
    this SUT must never be passed to `now_eval.harness.run_harness()`
    (which exercises all four surfaces); use `evaluate_search()`
    directly, as `now_search/cli.py`'s `eval` command does.
    """

    def __init__(self, search_engine: SearchEngine, bridge: WpIdBridge) -> None:
        self._engine = search_engine
        self._bridge = bridge

    @classmethod
    def build(cls, conn: Connection) -> "SearchEvalSUT":
        engine = SearchEngine(conn)
        engine.warm_up()
        bridge = WpIdBridge.load(conn)
        return cls(engine, bridge)

    def rank(self, query: str, candidate_ids: list[str], k: int) -> list[str]:
        candidate_set = set(candidate_ids)
        result = self._engine.search(query, k=k * OVERFETCH_MULTIPLIER, compute_facets=False)
        out: list[str] = []
        for hit in result.hits:
            db_id = int(hit.entity_id)
            wp_id = self._bridge.db_to_wp.get(db_id)
            if wp_id is None:
                continue
            wp_ref = f"wp:{wp_id}"
            if wp_ref in candidate_set:
                out.append(wp_ref)
            if len(out) >= k:
                break
        return out

    def related(self, article_id: str, candidate_ids: list[str], k: int) -> list[str]:
        raise NotImplementedError("Row 3 'similar' is E3.7 -- out of scope for E3.1's search SUT")

    def tag_facets(self, article_id: str) -> set[str]:
        raise NotImplementedError("facet tagging is E2.2 -- out of scope for E3.1's search SUT")

    def classify_type(self, article_id: str) -> str:
        raise NotImplementedError("type classification is E2.1 -- out of scope for E3.1's search SUT")
