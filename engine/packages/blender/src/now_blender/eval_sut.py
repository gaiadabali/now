"""Wires `BlenderReranker` into `now_eval`'s `SystemUnderTest` Protocol,
exactly mirroring `now_search.eval_sut.SearchEvalSUT` (including its
"why this adapter lives in the owning package, not under
`now_eval/sut/`" reasoning -- unchanged here, see that module's
docstring; the same import-shadowing problem applies verbatim to this
package). `now-eval` is a `dev`-only optional dependency (see
pyproject.toml, matching `now-search`'s own dev-extra) -- this module is
only imported by this package's own tests/CLI eval command, never by
production code.

**Deliberately does NOT use the synthetic format overlay.** `rank()`
below calls `BlenderReranker.rerank(..., synthetic_format_overlay=False)`
so the nDCG number this SUT produces is comparable, apples-to-apples,
to E3.1's own recorded number -- both measured against the exact same
real data, with no fabricated `format` values feeding the freshness term
that could otherwise inflate or deflate the score in a way that says
nothing about the blend's real quality. See README.md's "both nDCG
numbers" section for the actual comparison and why a synthetic-overlay
run is reported separately, as a decay-mechanism hand-check, never
folded into this number.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.engine import Connection

from now_blender.reranker import BlenderReranker

_WP_ID_MAP_SQL = text("SELECT id, legacy_wp_id FROM public.articles WHERE legacy_wp_id IS NOT NULL")

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


class BlenderEvalSUT:
    """Duck-types `now_eval.sut.SystemUnderTest` for the `search` surface
    only -- `related`/`tag_facets`/`classify_type` are out of scope
    (E3.5-3.7, E2.2, E2.1 respectively), same as `SearchEvalSUT`."""

    def __init__(self, reranker: BlenderReranker, bridge: WpIdBridge, *, log_features: bool = False) -> None:
        self._reranker = reranker
        self._bridge = bridge
        self._log_features = log_features

    @classmethod
    def build(cls, conn: Connection, *, log_features: bool = False) -> "BlenderEvalSUT":
        reranker = BlenderReranker.build(conn)
        bridge = WpIdBridge.load(conn)
        return cls(reranker, bridge, log_features=log_features)

    def rank(self, query: str, candidate_ids: list[str], k: int) -> list[str]:
        candidate_set = set(candidate_ids)
        result = self._reranker.rerank(
            query,
            k=k,
            rerank_pool=max(k * OVERFETCH_MULTIPLIER, 100),
            synthetic_format_overlay=False,
            log_features=self._log_features,
        )
        out: list[str] = []
        for hit in result.hits:
            wp_id = self._bridge.db_to_wp.get(hit.entity_id)
            if wp_id is None:
                continue
            wp_ref = f"wp:{wp_id}"
            if wp_ref in candidate_set:
                out.append(wp_ref)
            if len(out) >= k:
                break
        return out

    def related(self, article_id: str, candidate_ids: list[str], k: int) -> list[str]:
        raise NotImplementedError("Row 3 'similar' is E3.7 -- out of scope for this blend's search SUT")

    def tag_facets(self, article_id: str) -> set[str]:
        raise NotImplementedError("facet tagging is E2.2 -- out of scope for this blend's search SUT")

    def classify_type(self, article_id: str) -> str:
        raise NotImplementedError("type classification is E2.1 -- out of scope for this blend's search SUT")
