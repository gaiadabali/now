"""Bridges this async FastAPI app to `now_rails`, which is -- like the
whole `{now_search, now_filters, now_blender}` stack it composes --
deliberately **sync** (`sqlalchemy.engine.Connection`), not async. See
`now_rails.connections`'s own docstring for why that stack stays sync
rather than mixing an event loop into a call path several packages deep.

This module owns a small, process-local cache of sync `Engine` objects
(one per city `db_ref`, one for the platform DB), each with a real
connection pool of its own -- so a request pays for a `create_engine()`
call (cheap: it does not connect) at most once per `db_ref`, never once
per request. `app/infra/db/pools.CityPoolRegistry` is this app's existing
equivalent for the ASYNC pools `Depends(get_city_db)` hands out; this is
its sync-side sibling.

It lived in `app/domain/rails/` while rails was the only route needing a
sync bridge; `GET /v1/{site}/search` is the second (`now_search` is part
of the same sync stack), so it moved here to `app/infra/db/` rather than
have one domain package import another domain's internals. The engine
cache is keyed by `db_ref` and shared across both routes, which is the
point -- two routes hitting the same city now share one connection pool
instead of opening a second.

The actual rail computation runs via `asyncio.to_thread` so it never
blocks the event loop -- FastAPI's other routes keep serving traffic
while a rails request is doing synchronous Postgres I/O in a worker
thread.
"""

from __future__ import annotations

import asyncio
import threading
from collections.abc import Callable
from typing import TypeVar

from now_rails.connections import city_engine, platform_engine
from sqlalchemy import Engine

_lock = threading.Lock()
_city_engines: dict[str, Engine] = {}
_platform_engine: Engine | None = None

T = TypeVar("T")


def get_sync_city_engine(db_ref: str) -> Engine:
    with _lock:
        engine = _city_engines.get(db_ref)
        if engine is None:
            engine = city_engine(db_ref)
            _city_engines[db_ref] = engine
        return engine


def get_sync_platform_engine() -> Engine:
    global _platform_engine
    with _lock:
        if _platform_engine is None:
            _platform_engine = platform_engine()
        return _platform_engine


async def run_sync(fn: Callable[[], T]) -> T:
    """Runs a zero-arg sync callable off the event loop. Thin wrapper
    (not just a bare `asyncio.to_thread(fn)` at every call site) so
    there is exactly one place to add e.g. a thread-pool size limit or
    per-call timeout later without touching every caller."""
    return await asyncio.to_thread(fn)


def dispose_all() -> None:
    """Test/shutdown seam -- disposes every cached sync engine. Not
    wired into `app.main`'s lifespan (out of this ticket's scope to
    touch); a process restart is today's disposal mechanism, matching
    every sync-package CLI in this repo (`now-search`, `now-filters`,
    `now-blender` CLIs all create-and-forget an `Engine` per invocation
    too)."""
    global _platform_engine
    with _lock:
        for engine in _city_engines.values():
            engine.dispose()
        _city_engines.clear()
        if _platform_engine is not None:
            _platform_engine.dispose()
            _platform_engine = None
