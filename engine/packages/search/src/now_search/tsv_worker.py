"""Keep-fresh worker for `engine.article_search` (F41): consumes
`article.published` / `article.republished` off the same Redis **Stream**
`now:domain-events:stream` that `now-embeddings`'s `ReembedWorker` already
reads, per ARCHITECTURE.md's "publish hook" and the exact contract
`engine/packages/cms/src/lib/redis.ts` emits (not owned by this package --
read there, never edited).

**Own consumer group, on purpose.** `GROUP = "now-search-tsv-worker"`,
distinct from `now-embeddings`'s `"now-embeddings-worker"`. Redis Streams
consumer-group semantics: each *group* receives its own independent copy
of every message appended to the stream (`XREADGROUP` fans out per group,
not per consumer process) -- two workers sharing one group would each get
only a fraction of the messages (steal each other's work); two workers on
two groups each see every message exactly once, independently. This is
what the task brief means by "use a separate consumer group so the two
workers don't steal each other's messages" -- verified by reading the
Streams consumer-group model, not assumed. Same at-least-once delivery
guarantee as `now-embeddings`'s worker (`XREADGROUP` + `XACK`; an
unacknowledged message stays claimable after a crash) -- see that
module's docstring for the full "why a Stream, not pub/sub" reasoning,
which applies identically here.

**Article-only, deliberately.** `engine.article_search` only exists for
`public.articles` (migration 0006's spec) -- unlike `now-embeddings`'s
worker, which also handles `place.published`/`place.republished`, this
worker's `REFRESH_EVENTS` omits the place events entirely, and
`handle_payload` ignores any event whose `entity_type != "article"`. This
is a scope decision, not an oversight: places have no body prose for a
lexical tsvector to index in the first place (see
`now_embeddings.textbuild.build_place_text`'s docstring -- places embed
structured fields, not free text).

**Multi-tenant routing**, identical to `now_embeddings.worker`: the event
payload carries `site_slug`, looked up against `now_platform.engine.sites`
via `now_db.sites_registry.get_site` to resolve a `db_ref` -- no site
slug is ever hardcoded here (ARCHITECTURE.md §3.5). An unknown slug is
logged and ACKed, not requeued forever.
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
from now_search.connections import city_engine, platform_engine
from now_search.tsv_pipeline import fetch_one, refresh_row

logger = logging.getLogger("now_search.tsv_worker")

STREAM = "now:domain-events:stream"
GROUP = "now-search-tsv-worker"  # distinct from now-embeddings' "now-embeddings-worker" -- see module docstring
REFRESH_EVENTS = {"article.published", "article.republished"}


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
class TsvWorkerResult:
    processed: int = 0
    updated: int = 0
    skipped_unchanged: int = 0
    ignored: int = 0
    errors: int = 0


class TsvRefreshWorker:
    """Holds the (small) per-site_slug engine cache and the site-registry
    lookup so a long-running `--follow` loop doesn't reconnect to
    Postgres per message -- same shape as `now_embeddings.worker.ReembedWorker`."""

    def __init__(self, redis_url: str | None = None) -> None:
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
        if name not in REFRESH_EVENTS:
            return "ignored:event"
        entity_type = event.get("entity_type")
        if entity_type != "article":
            return f"ignored:entity_type={entity_type}"

        raw_id = event.get("entity_id")
        try:
            article_id = int(raw_id)
        except (TypeError, ValueError):
            logger.warning("non-integer entity_id=%r on event %s -- ACKing without indexing", raw_id, name)
            return f"ignored:bad_entity_id={raw_id!r}"

        site_slug = event.get("site_slug")
        engine = self._engine_for_slug(site_slug) if site_slug else None
        if engine is None:
            logger.warning("unknown site_slug=%r on event %s -- ACKing without indexing", site_slug, name)
            return f"ignored:unknown_site_slug={site_slug}"

        row = fetch_one(engine, article_id)
        if row is None:
            logger.info("article:%s not found (or not published) -- nothing to index", article_id)
            return "ignored:not_found"

        updated = refresh_row(engine, row)
        logger.info(
            "%s article:%s (site=%s) -> %s",
            name,
            article_id,
            site_slug,
            "tsv updated" if updated else "unchanged, skipped",
        )
        return "updated" if updated else "skipped_unchanged"

    def run_once(self, *, block_ms: int = 2000, count: int = 50, consumer: str | None = None) -> TsvWorkerResult:
        """Reads whatever is currently pending/new on the stream for this
        consumer group, processes it, ACKs, and returns. Used by
        `tsv-worker --once` (CLI) and by tests -- a bounded, deterministic
        unit of work rather than an infinite loop."""
        consumer_name = consumer or f"worker-{os.getpid()}"
        result = TsvWorkerResult()
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
                    if status == "updated":
                        result.updated += 1
                    elif status == "skipped_unchanged":
                        result.skipped_unchanged += 1
                    else:
                        result.ignored += 1
                finally:
                    # ACK regardless of outcome: a permanently malformed message
                    # must not wedge the consumer group forever. Errors are
                    # logged above and surfaced in `result.errors` for the
                    # caller to alert on -- ACK means "delivered and
                    # attempted", not "succeeded".
                    self.redis.xack(STREAM, GROUP, message_id)
        return result

    def run_forever(self, *, poll_interval_s: float = 1.0) -> None:  # pragma: no cover -- infinite loop
        logger.info("now-search tsv worker started, consuming %s (group=%s)", STREAM, GROUP)
        while True:
            result = self.run_once(block_ms=5000)
            if result.processed == 0:
                time.sleep(poll_interval_s)
