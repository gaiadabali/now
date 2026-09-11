"""The Sec.7 "personalized re-rank ... over the top ~40" seam.

Segments (~20 coarse taste segments, E7.4) and per-user taste vectors
(E7.2) don't exist yet -- `RailsOrchestrator` always computes/caches
against `DEFAULT_SEGMENT` (`now_rails.models.DEFAULT_SEGMENT = "default"`).
`rerank_for_user` below is the explicit no-op this ticket's brief asked
for ("make the seam obvious") rather than a TODO comment: its signature
already takes a `user_vector`, and a future caller (E7.2+) supplies a real
one without this module's shape changing. Until then it returns its input
unchanged -- a real dot product over ~40 cached rows, per Sec.7's own
"sub-millisecond" characterisation, once there is a vector to dot against.
"""

from __future__ import annotations

from now_rails.models import RailItem


def rerank_for_user(items: list[RailItem], *, user_vector: list[float] | None = None) -> list[RailItem]:
    if user_vector is None:
        return items
    # E7.2 not built -- no taste vector exists to dot against yet. When it
    # does, this is where a per-item embedding lookup + dot product +
    # re-sort over the (small, cached) `items` list belongs.
    return items
