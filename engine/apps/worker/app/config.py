"""Worker settings.

Plain dataclass + os.environ rather than pydantic-settings: this app has no
HTTP surface and a handful of values, and adding a dependency to parse six
environment variables is not a trade worth making. The API uses
pydantic-settings because it has ~20 and serves them over a request path.

Prefix is `ENGINE_WORKER_`, matching the API's `ENGINE_API_` convention so
that a compose file reads consistently and an unprefixed variable is
obviously not ours.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

DEFAULT_PLATFORM_DSN = "postgresql+psycopg://now:now@localhost:5432/now_platform"
DEFAULT_REDIS_URL = "redis://localhost:6379/0"

HEARTBEAT_KEY = "now:worker:heartbeat"


def _int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer, got {raw!r}") from exc


#: Everything not in here is true, including the empty string — compose
#: passes an unset variable as `""` and "not configured" must mean "on" for
#: both flags below, not "silently off".
_FALSEY = {"0", "false", "no"}


def _bool(name: str, default: bool = True) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() not in _FALSEY


def _optional_int(name: str) -> int | None:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return None
    try:
        return int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer or unset, got {raw!r}") from exc


@dataclass(frozen=True)
class Settings:
    platform_database_url: str = DEFAULT_PLATFORM_DSN
    redis_url: str = DEFAULT_REDIS_URL
    log_level: str = "INFO"

    partition_days_ahead: int = 14
    # None means "never drop". See jobs.DEFAULT_RETENTION_DAYS for why that
    # is the default and not a number.
    interaction_retention_days: int | None = None

    # Whether this process also runs the domain-event stream consumer
    # (app.consumer.DomainEventWorker) in a supervised thread. On by
    # default: one container is cheaper than two on a 2 vCPU / 7 GB box, and
    # the consumer is IO-bound. Turn it off to run it as its own service.
    #
    # The name is `..._RUN_REEMBED_CONSUMER` and stays that way: it is what
    # `deploy/docker-compose.yml` already sets on the live box, and renaming
    # it would silently fall back to the default on the next deploy. The
    # thread it gates now carries the classification handler too.
    run_reembed_consumer: bool = True
    reembed_provider: str = "local"

    # Whether that same consumer also applies `classification.reviewed` into
    # `engine.entity_terms` (app/classification.py). Its own switch, not a
    # second copy of the one above: the two handlers share a thread, so
    # turning re-embedding off to move it to its own service would otherwise
    # silently take the review path with it. Kept as `ENGINE_WORKER_*` with
    # the same true-by-default parsing as its neighbour, so a compose file
    # that says nothing gets the behaviour this ticket exists to deliver.
    apply_classification_reviews: bool = True

    heartbeat_key: str = HEARTBEAT_KEY
    heartbeat_ttl_seconds: int = 180

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            platform_database_url=os.environ.get(
                "ENGINE_WORKER_PLATFORM_DATABASE_URL", DEFAULT_PLATFORM_DSN
            ),
            redis_url=os.environ.get("ENGINE_WORKER_REDIS_URL", DEFAULT_REDIS_URL),
            log_level=os.environ.get("ENGINE_WORKER_LOG_LEVEL", "INFO").upper(),
            partition_days_ahead=_int("ENGINE_WORKER_PARTITION_DAYS_AHEAD", 14),
            interaction_retention_days=_optional_int(
                "ENGINE_WORKER_INTERACTION_RETENTION_DAYS"
            ),
            run_reembed_consumer=_bool("ENGINE_WORKER_RUN_REEMBED_CONSUMER"),
            apply_classification_reviews=_bool("ENGINE_WORKER_APPLY_CLASSIFICATION_REVIEWS"),
            reembed_provider=os.environ.get("ENGINE_WORKER_REEMBED_PROVIDER", "local"),
            heartbeat_ttl_seconds=_int("ENGINE_WORKER_HEARTBEAT_TTL_SECONDS", 180),
        )
