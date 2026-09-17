"""One stream consumer, two concerns.

`now_embeddings.worker.ReembedWorker` is the only domain-event consumer this
process actually starts, and it has the whole of the delivery contract
already worked out: the Stream rather than pub/sub (so a restart does not
lose an editor's save), the consumer group, the per-message try/except, and
the `XACK`-in-`finally` that keeps a poison message from wedging the group
forever. `classification.reviewed` needs exactly that contract and nothing
new, so this subclasses it instead of standing up a second loop.

**That choice is not theoretical tidiness.** The repository already contains
the alternative: `now_search.tsv_worker` is a second, near-identical
consumer with its own group, written for `article.published`. Nothing in
`app/main.py` starts it. Its group is registered on the live stream with a
double-digit backlog it will never read. A consumer that no process runs is
indistinguishable from a consumer that was never written, which is the
condition this module exists to fix for classification decisions -- so the
one rule here is that the code lives where the running thread already is.

**The group name stays `now-embeddings-worker`.** It is now a misnomer: that
group also applies classification decisions. Renaming it would create a new
consumer group, and a new group is created at id `0` -- it would replay the
entire stream history and re-embed every article ever published. The
accurate name is not worth that, and a comment costs nothing. Redis fans
out per *group*, so this remains exactly-once for this process.

`handle_payload` is the one seam: the base class's `run_once` calls it per
message and interprets the returned status, and everything it does not
recognise is counted as `ignored` -- which is true enough (nothing was
re-embedded) and is why this module logs the classification outcome itself
rather than relying on the caller's counters.
"""

from __future__ import annotations

import logging

from now_embeddings.worker import ReembedWorker

from app import classification

logger = logging.getLogger("app.consumer")


class DomainEventWorker(ReembedWorker):
    """`ReembedWorker` plus the `classification.reviewed` handler.

    Reuses the base class's site-registry cache and per-city engine pool
    (`_engine_for_slug`) rather than opening its own: both handlers route on
    the same `site_slug` field and a second pool would double the
    connections a 2 vCPU box holds open for no gain.

    `_facet_shapes` is cached for the same reason the base caches `db_ref`:
    the platform vocabulary is seeded, changes on the order of never, and a
    reviewer clearing a queue emits one event per click -- a platform round
    trip per click to re-read eleven facet rows would be the dominant cost of
    the whole path. A facet added to the vocabulary mid-process is picked up
    on restart; a facet is not something an editor creates.
    """

    def __init__(self, *args, apply_classification_reviews: bool = True, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.apply_classification_reviews = apply_classification_reviews
        self._facet_shapes: dict[str, classification.FacetShape | None] = {}

    def _facet_shape(self, facet_key: str) -> classification.FacetShape | None:
        if facet_key not in self._facet_shapes:
            self._facet_shapes[facet_key] = classification.load_facet_shape(
                self._platform_engine, facet_key
            )
        return self._facet_shapes[facet_key]

    def handle_payload(self, event: dict) -> str:
        if event.get("event") != classification.EVENT:
            return super().handle_payload(event)
        if not self.apply_classification_reviews:
            # Ack and drop, not requeue: leaving these pending would build a
            # backlog that replays in one burst whenever the flag flips back.
            logger.info("%s ignored -- handler disabled by configuration", classification.EVENT)
            return "ignored:classification_disabled"
        return self._handle_classification_reviewed(event)

    def _handle_classification_reviewed(self, event: dict) -> str:
        try:
            decision = classification.decision_from(event)
        except classification.UnusableEvent as exc:
            # WARNING, not an exception: the base class's handler would count
            # a raise as an error and log a traceback, and a traceback implies
            # something to retry. There is nothing to retry -- the event is
            # malformed or the CMS could not resolve a term -- so this is
            # reported as a fact about the event, loudly enough to notice.
            logger.warning("%s unusable, ACKing: %s -- event=%r", classification.EVENT, exc, event)
            return f"ignored:unusable ({exc})"

        city = self._engine_for_slug(decision.site_slug) if decision.site_slug else None
        if city is None:
            # Same stance as the base class for an unknown slug: a config
            # problem on the publishing side is not a reason to wedge a
            # consumer group shared with the re-embed path.
            logger.warning(
                "%s for unknown site_slug=%r -- ACKing without applying (review=%s)",
                classification.EVENT,
                decision.site_slug,
                decision.review_id,
            )
            return f"ignored:unknown_site_slug={decision.site_slug}"

        shape = self._facet_shape(decision.facet_key)
        if shape is None:
            # A facet the platform vocabulary does not have. Retrying cannot
            # help -- the fix is a vocabulary seed, not another delivery.
            logger.warning(
                "%s names facet_key=%r, absent from the platform vocabulary -- ACKing (review=%s)",
                classification.EVENT,
                decision.facet_key,
                decision.review_id,
            )
            return f"ignored:unknown_facet={decision.facet_key}"

        return classification.apply_decision(city, shape, decision)
