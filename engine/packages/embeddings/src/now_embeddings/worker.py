"""Re-embed-on-publish worker: consumes `article.published` (and
`article.republished` / `place.published` / `place.republished`, same
handling -- a republish can change title/dek/body just as much as a first
publish) off the Redis **Stream** `now:domain-events:stream`, per
ARCHITECTURE.md's "publish hook" and the exact contract
`engine/packages/cms/src/lib/redis.ts` emits (not owned by this package --
read there, never edited).

**Stream, not pub/sub, on purpose.** The CMS hook (`publishDomainEvent`)
writes to both a pub/sub channel and a Stream in parallel specifically so
"the worker team can pick either" (its own docstring). Pub/sub delivers
only to subscribers connected *at publish time* -- a worker that is
restarting, deploying, or briefly down loses the message forever. A Stream
consumer group (`XREADGROUP` + `XACK`) gives at-least-once delivery: an
unacknowledged message stays claimable after a crash (`XPENDING` /
`XCLAIM`, not implemented in this v1 -- see README "Not implemented"), and
`XREADGROUP ... > `always resumes from exactly where this consumer group
left off, which is the literal definition of the task's "resumable"
requirement applied to the worker rather than the backfill.

**Multi-tenant routing.** The event payload carries `site_slug`
("jakarta"/"bali"/"test" today, per `now_platform.engine.sites` -- ARCHITECTURE.md
§3.5 forbids hardcoding any of those names in engine code, and this module
doesn't: it looks up `site_slug -> db_ref` from the registry, generically,
for whatever slug the event contains). An unknown slug is logged and
ACKed (not requeued forever) -- a config problem on the CMS side, not a
reason to wedge this consumer group.
"""

from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass

import redis
from sqlalchemy import Engine

from now_db.sites_registry import get_site
from now_embeddings.connections import city_engine, platform_engine
from now_embeddings.pipeline import fetch_one, reembed_one
from now_embeddings.providers.base import EmbeddingProvider

logger = logging.getLogger("now_embeddings.worker")

STREAM = "now:domain-events:stream"
GROUP = "now-embeddings-worker"
REEMBED_EVENTS = {
    "article.published",
    "article.republished",
    "place.published",
    "place.republished",
}
REEMBEDDABLE_ENTITY_TYPES = {"article", "place"}


def redis_client(redis_url: str | None = None) -> redis.Redis:
    url = redis_url or os.environ.get("REDIS_URL", "redis://localhost:16379/0")
    return redis.Redis.from_url(url, decode_responses=True)


def ensure_group(r: redis.Redis) -> None:
    try:
        r.xgroup_create(STREAM, GROUP, id="0", mkstream=True)
    except redis.ResponseError as exc:
        if "BUSYGROUP" not in str(exc):
            raise


@dataclass
class WorkerResult:
    processed: int = 0
    reembedded: int = 0
    skipped_unchanged: int = 0
    ignored: int = 0
    errors: int = 0


class ReembedWorker:
    """Holds the (small) per-site_slug engine cache and the site-registry
    lookup so a long-running `--follow` loop doesn't reconnect to Postgres
    per message."""

    def __init__(self, provider: EmbeddingProvider, redis_url: str | None = None) -> None:
        self.provider = provider
        self.redis = redis_client(redis_url)
        self._platform_engine = platform_engine()
        self._city_engines: dict[str, Engine] = {}
        self._db_ref_cache: dict[str, str | None] = {}
        ensure_group(self.redis)

    def _db_ref_for_slug(self, site_slug: str) -> str | None:
        if site_slug not in self._db_ref_cache:
            with self._platform_engine.connect() as conn:
                site = get_site(conn, site_slug)
            self._db_ref_cache[site_slug] = site.db_ref if site else None
        return self._db_ref_cache[site_slug]

    def _engine_for_slug(self, site_slug: str) -> Engine | None:
        db_ref = self._db_ref_for_slug(site_slug)
        if db_ref is None:
            return None
        if db_ref not in self._city_engines:
            self._city_engines[db_ref] = city_engine(db_ref)
        return self._city_engines[db_ref]

    def handle_payload(self, event: dict) -> str:
        """Processes one already-decoded domain event. Returns a short
        status string (used by tests and CLI logging)."""
        name = event.get("event")
        if name not in REEMBED_EVENTS:
            return "ignored:event"
        entity_type = event.get("entity_type")
        if entity_type not in REEMBEDDABLE_ENTITY_TYPES:
            return f"ignored:entity_type={entity_type}"
        entity_id = str(event.get("entity_id"))
        site_slug = event.get("site_slug")
        engine = self._engine_for_slug(site_slug) if site_slug else None
        if engine is None:
            logger.warning("unknown site_slug=%r on event %s -- ACKing without re-embedding", site_slug, name)
            return f"ignored:unknown_site_slug={site_slug}"

        row = fetch_one(engine, entity_type, entity_id)
        if row is None:
            logger.info("%s:%s not found (or not published) -- nothing to embed", entity_type, entity_id)
            return "ignored:not_found"

        changed = reembed_one(engine, entity_type=entity_type, row=row, provider=self.provider)
        logger.info(
            "%s %s:%s (site=%s) -> %s",
            name,
            entity_type,
            entity_id,
            site_slug,
            "re-embedded" if changed else "unchanged, skipped model call",
        )
        return "reembedded" if changed else "skipped_unchanged"

    def run_once(self, *, block_ms: int = 2000, count: int = 50, consumer: str | None = None) -> WorkerResult:
        """Reads whatever is currently pending/new on the stream for this
        consumer group, processes it, ACKs, and returns. Used by `worker
        --once` (CLI) and by tests -- a bounded, deterministic unit of
        work rather than an infinite loop."""
        consumer_name = consumer or f"worker-{os.getpid()}"
        result = WorkerResult()
        entries = self.redis.xreadgroup(GROUP, consumer_name, {STREAM: ">"}, count=count, block=block_ms)
        for _stream_name, messages in entries or []:
            for message_id, fields in messages:
                result.processed += 1
                try:
                    event = json.loads(fields["event"])
                    status = self.handle_payload(event)
                except Exception:  # noqa: BLE001 -- one bad message must not stop the batch
                    logger.exception("failed to process message %s", message_id)
                    result.errors += 1
                else:
                    if status == "reembedded":
                        result.reembedded += 1
                    elif status == "skipped_unchanged":
                        result.skipped_unchanged += 1
                    else:
                        result.ignored += 1
                finally:
                    # ACK regardless of outcome: a permanently malformed message
                    # (e.g. bad JSON) must not wedge the consumer group forever.
                    # Errors are logged (see above) and surfaced in `result.errors`
                    # for the caller to alert on -- ACK means "delivered and
                    # attempted", not "succeeded".
                    self.redis.xack(STREAM, GROUP, message_id)
        return result

    def run_forever(self, *, poll_interval_s: float = 1.0) -> None:  # pragma: no cover -- infinite loop
        logger.info("now-embeddings worker started, consuming %s (group=%s)", STREAM, GROUP)
        while True:
            result = self.run_once(block_ms=5000)
            if result.processed == 0:
                time.sleep(poll_interval_s)
