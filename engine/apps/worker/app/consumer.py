"""One stream consumer, three concerns.

`now_embeddings.worker.ReembedWorker` is the only domain-event consumer this
process actually starts, and it has the whole of the delivery contract
already worked out: the Stream rather than pub/sub (so a restart does not
lose an editor's save), the consumer group, the per-message try/except, and
the `XACK`-in-`finally` that keeps a poison message from wedging the group
forever. `classification.reviewed` needed exactly that contract and nothing
new, so it was subclassed in rather than standing up a second loop; WS1's
`engine.hidden_rival_flags` freshness (Edition 2 third pass) needs the
identical thing for `article.published`/`.republished`/`.unpublished` and
joins the same class for the same reason.

**Why hidden-rival recompute lives HERE and not in a fourth consumer.** The
precomputed `engine.hidden_rival_flags` table (`now_filters
.hidden_rival_recompute`, migration 0009) exists so the article page's rail
queries never repeat the ~27ms live regex join measured against real data
(ARCHITECTURE.md §8.G) -- but a precomputed table is only as good as its
last recompute. Hooking into the SAME stream `article.published` already
rides means a fresh story is flagged within this process's own
at-least-once delivery, not tomorrow's cron (`app/jobs.py`'s nightly full
recompute is the safety net underneath this, not the primary mechanism --
see that job's own docstring).

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
from now_filters.hidden_rival_recompute import recompute_flags_for_article, remove_flags_for_article

from app import classification

logger = logging.getLogger("app.consumer")

# Edition 2, WS1 third pass: `engine.hidden_rival_flags` freshness. The base
# class's own `REEMBED_EVENTS` names the events that carry enough of the
# article to re-embed; this is a NARROWER set on purpose -- `place.published`/
# `place.republished` re-embed a place, not an article, and this table has
# nothing to say about a place row (see `now_filters.hidden_rival_recompute`'s
# module docstring, item 2, for why a place-mentions-only change has no event
# at all and is left to the nightly recompute instead).
HIDDEN_RIVAL_RECOMPUTE_EVENTS = {"article.published", "article.republished"}
HIDDEN_RIVAL_REMOVE_EVENTS = {"article.unpublished"}


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
        name = event.get("event")

        if name == classification.EVENT:
            if not self.apply_classification_reviews:
                # Ack and drop, not requeue: leaving these pending would build
                # a backlog that replays in one burst whenever the flag flips
                # back.
                logger.info("%s ignored -- handler disabled by configuration", classification.EVENT)
                return "ignored:classification_disabled"
            return self._handle_classification_reviewed(event)

        if name in HIDDEN_RIVAL_RECOMPUTE_EVENTS or name in HIDDEN_RIVAL_REMOVE_EVENTS:
            # Both this handler AND the base class's own re-embed handler
            # want `article.published`/`.republished` -- neither replaces the
            # other, so both run. `article.unpublished` is not in the base
            # class's `REEMBED_EVENTS`, so `super().handle_payload` harmlessly
            # returns `ignored:event` for it; this handler is the only one
            # that does anything with it.
            hidden_rival_status = self._handle_hidden_rival(event, name)
            base_status = super().handle_payload(event)
            return f"{base_status}+hidden_rival:{hidden_rival_status}"

        return super().handle_payload(event)

    def _handle_hidden_rival(self, event: dict, name: str) -> str:
        """The fast path for `engine.hidden_rival_flags` freshness (WS1
        third pass): one article, recomputed or removed within this same
        at-least-once delivery, rather than waiting for the nightly full
        recompute (`app/jobs.py`). Never raises out to the caller -- a
        failure here must not turn into an unhandled exception that the
        base class's own `run_once` would otherwise catch and count as
        `errors` under a misleading traceback; this handler reports its
        own failure as a status string instead, exactly like
        `_handle_classification_reviewed` does above.
        """
        entity_type = event.get("entity_type")
        if entity_type != "article":
            # `place.published`/`.republished` never reach here (see
            # `HIDDEN_RIVAL_RECOMPUTE_EVENTS`'s own comment) -- this branch
            # is a defensive no-op for a payload shaped unexpectedly, not a
            # code path this repository's own events can reach today.
            return f"ignored:entity_type={entity_type}"

        entity_id = event.get("entity_id")
        site_slug = event.get("site_slug")
        engine = self._engine_for_slug(site_slug) if site_slug else None
        if engine is None:
            logger.warning(
                "%s for unknown site_slug=%r -- ACKing without recomputing hidden-rival flags (article=%s)",
                name,
                site_slug,
                entity_id,
            )
            return f"ignored:unknown_site_slug={site_slug}"

        try:
            with engine.begin() as conn:
                if name in HIDDEN_RIVAL_REMOVE_EVENTS:
                    removed = remove_flags_for_article(conn, entity_id)
                    logger.info("%s article:%s (site=%s) -> removed %d hidden-rival flag row(s)", name, entity_id, site_slug, removed)
                    return f"removed={removed}"
                report = recompute_flags_for_article(conn, entity_id)
                logger.info(
                    "%s article:%s (site=%s) -> hidden-rival flags added=%d removed=%d unchanged=%d",
                    name,
                    entity_id,
                    site_slug,
                    report.added,
                    report.removed,
                    report.unchanged,
                )
                return f"added={report.added} removed={report.removed}"
        except Exception:  # noqa: BLE001 -- reported as a status string, not re-raised (see docstring)
            logger.exception("hidden-rival recompute failed for article:%s (site=%s)", entity_id, site_slug)
            return "error"

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
