"""`RailsOrchestrator` -- the E3.8 integration point. Resolves the subject
once, computes whichever of the three rails are missing/stale from
`engine.rail_cache`, and returns a `RailsBundle` (ARCHITECTURE.md Sec.16's
`GET /v1/{site}/articles/{id}/rails`).

**Warm path calls no embedder, ever.** A cache HIT for all three rails
returns straight from `engine.rail_cache` -- no subject fetch, no
`now_filters`/`now_blender` call, no `engine.embeddings` query. This is
deliberate given F53 (`query_embedder`'s ONNX load dominates p95 on every
other path in this codebase that touches it): none of Row 1/2/3 embed a
text query at all (Row 3 reads the subject's *already-stored* vector,
Row 1/2 never touch embeddings except for MMR's stored-vector cosine
similarity), so the only way this package's p95 could regress toward that
cost is a bug, not an inherited default. See the package README's timing
section for measured warm-vs-cold numbers.

**Personalized re-rank (Sec.7 "personalized re-rank ... over the top
~40")** is a no-op identity pass today -- `personalize.py`'s
`rerank_for_user` -- because segments/user taste vectors don't exist yet
(E7.1/E7.2). The seam is the function signature, not a TODO comment: a
future caller passes a real `user_vector` and this module's shape does
not change.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime, timezone

from now_blender.platform import DEFAULT_SITE_RANKING_CONFIG, SiteRankingConfig, load_site_ranking_config
from now_filters.type_relations import TypeRelation
from sqlalchemy.engine import Connection

from now_rails.cache import CachedRail, is_fresh, read_cached_rails, write_rail_caches
from now_rails.models import RAIL_NAMES, ROW1, ROW2, ROW3, DEFAULT_SEGMENT, RailResult, RailTiming, RailsBundle
from now_rails.relations_cache import load_type_relations_cached
from now_rails.row1_complementary import compute_row1
from now_rails.row2_nearby import compute_row2
from now_rails.row3_similar import compute_row3
from now_rails.subject import ArticleSubject, fetch_article_subject


class ArticleNotFoundError(Exception):
    """No published article with this id -- callers map this to a 404."""


@dataclass(frozen=True)
class RailsOrchestrator:
    conn: Connection
    relations: dict[str, TypeRelation]
    site_config: SiteRankingConfig

    @classmethod
    def build(
        cls,
        city_conn: Connection,
        *,
        platform_conn: Connection | None = None,
        site_slug: str | None = None,
    ) -> "RailsOrchestrator":
        """Mirrors `now_blender.reranker.BlenderReranker.build` one for
        one: give both `platform_conn`/`site_slug` for live
        `sites.ranking_weights`, or omit both for the package default.

        `type_relations` is read through `relations_cache` (5-minute TTL,
        keyed by the connection's database name) rather than queried
        fresh every call -- see that module's docstring for why this
        static-in-practice, 8-9-row table is worth caching on the p95
        path."""
        cache_key = city_conn.engine.url.database or "default"
        try:
            relations = load_type_relations_cached(city_conn, cache_key=cache_key)
        except Exception:  # noqa: BLE001 -- engine.type_relations may not exist in every test DB
            relations = {}
        if platform_conn is not None and site_slug is not None:
            config = load_site_ranking_config(platform_conn, site_slug)
        else:
            config = DEFAULT_SITE_RANKING_CONFIG
        return cls(conn=city_conn, relations=relations, site_config=config)

    def _compute_fresh(
        self, subject: ArticleSubject, *, k: int, rerank_pool: int, synthetic_overlay: bool, now: datetime | None
    ) -> dict[str, RailResult]:
        return {
            ROW1: compute_row1(self.conn, subject, self.relations, site_config=self.site_config, k=k, rerank_pool=rerank_pool, now=now),
            ROW2: compute_row2(self.conn, subject, self.relations, site_config=self.site_config, k=k, rerank_pool=rerank_pool, now=now),
            ROW3: compute_row3(
                self.conn, subject, self.relations, site_config=self.site_config, k=k, rerank_pool=rerank_pool,
                synthetic_format_overlay=synthetic_overlay, now=now,
            ),
        }

    def compute_rails(
        self,
        article_id: int,
        *,
        segment: str = DEFAULT_SEGMENT,
        k: int = 6,
        rerank_pool: int = 40,
        synthetic_overlay: bool = False,
        force_refresh: bool = False,
        max_age=None,
        now: datetime | None = None,
    ) -> RailsBundle:
        """`synthetic_overlay=True` overlays a deterministic
        `primary_type` (F50) onto the subject article AND a deterministic
        `format` onto Row 3's candidates -- see `subject.py`/
        `row3_similar.py`. **Never cached** when `synthetic_overlay=True`
        (a synthetic result must never be served back to a real request
        that didn't ask for one) -- see the `force_refresh`/no-write logic
        below.
        """
        t_start = time.perf_counter()
        from_kwargs = dict(max_age=max_age) if max_age is not None else {}

        if not force_refresh and not synthetic_overlay:
            cached = read_cached_rails(self.conn, article_id, segment, list(RAIL_NAMES))
            if len(cached) == len(RAIL_NAMES) and all(is_fresh(c, **from_kwargs) for c in cached.values()):
                computed_at = min(c.computed_at for c in cached.values())
                total_ms = (time.perf_counter() - t_start) * 1000
                return RailsBundle(
                    article_id=article_id,
                    segment=segment,
                    rails={name: c.result for name, c in cached.items()},
                    cache_hit=True,
                    computed_at=computed_at,
                    timing=RailTiming(subject_ms=0.0, row1_ms=0.0, row2_ms=0.0, row3_ms=0.0, total_ms=total_ms),
                    synthetic_overlay=False,
                )

        t0 = time.perf_counter()
        subject = fetch_article_subject(self.conn, article_id, synthetic_type_overlay=synthetic_overlay)
        subject_ms = (time.perf_counter() - t0) * 1000
        if subject is None:
            raise ArticleNotFoundError(f"no published article with id={article_id}")

        t1 = time.perf_counter()
        row1 = compute_row1(self.conn, subject, self.relations, site_config=self.site_config, k=k, rerank_pool=rerank_pool, now=now)
        row1_ms = (time.perf_counter() - t1) * 1000

        t2 = time.perf_counter()
        row2 = compute_row2(self.conn, subject, self.relations, site_config=self.site_config, k=k, rerank_pool=rerank_pool, now=now)
        row2_ms = (time.perf_counter() - t2) * 1000

        t3 = time.perf_counter()
        row3 = compute_row3(
            self.conn, subject, self.relations, site_config=self.site_config, k=k, rerank_pool=rerank_pool,
            synthetic_format_overlay=synthetic_overlay, now=now,
        )
        row3_ms = (time.perf_counter() - t3) * 1000

        computed_at = now or datetime.now(timezone.utc)
        rails = {ROW1: row1, ROW2: row2, ROW3: row3}

        if not synthetic_overlay:
            write_rail_caches(self.conn, article_id, segment, list(rails.values()), now=computed_at)

        total_ms = (time.perf_counter() - t_start) * 1000
        return RailsBundle(
            article_id=article_id,
            segment=segment,
            rails=rails,
            cache_hit=False,
            computed_at=computed_at,
            timing=RailTiming(subject_ms=subject_ms, row1_ms=row1_ms, row2_ms=row2_ms, row3_ms=row3_ms, total_ms=total_ms),
            synthetic_overlay=synthetic_overlay,
        )
