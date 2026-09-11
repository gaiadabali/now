"""Serve-time logging of the Sec.10 stage-4 feature vector.

**No table exists for this, and this package writes no migration** (task
scope: "Do NOT touch ... Write no migration"). `engine.impressions`
(the only serve-time-logging table that exists) is shaped for
click/impression beacon events (`session_id`, `anon_id`, `entity_id
uuid`, `position`) -- it has no columns for a 16-field feature vector and
its `entity_id` is `uuid`, not the `text`-stringified-int convention
this package's candidates use (F33). Extending it, or adding a new
`engine.ranking_features` table, is a schema decision for the DB-owning
agent, not this ticket.

So this module logs structured JSON lines through Python's standard
`logging` module instead -- a real, inspectable, machine-parseable
record emitted on every `rerank()` call, immediately usable (grep/`jq`
a log file, or ship it through whatever log pipeline already exists)
and trivially promotable to a real ingestion job the day a table exists:
point a consumer at this logger's output and `INSERT` each line's
`features` dict. This satisfies "log ... so six months of these is what
makes the LambdaMART re-ranker possible later" without inventing schema
this ticket has no authority to create.

Logger name: `now_blender.feature_log`. One JSON object per line
(easy `jsonlines`/`jq` consumption), one line per (query, candidate)
pair, emitted at INFO level so it can be routed independently of this
package's other (DEBUG-level, ordinary diagnostic) logging.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone

from now_blender.features import StageFourFeatures

LOGGER_NAME = "now_blender.feature_log"

logger = logging.getLogger(LOGGER_NAME)


@dataclass(frozen=True)
class FeatureLogRecord:
    ts: str
    site_slug: str
    surface: str  # "search" | "row1_complementary" | "row2_nearby" | "row3_similar"
    query: str | None
    subject_entity_id: str | None
    entity_type: str
    entity_id: int
    blend_score: float
    weights_source: str
    features: dict


def build_record(
    *,
    site_slug: str,
    surface: str,
    query: str | None,
    subject_entity_id: str | None,
    entity_type: str,
    entity_id: int,
    blend_score: float,
    weights_source: str,
    features: StageFourFeatures,
    now: datetime | None = None,
) -> FeatureLogRecord:
    ts = (now or datetime.now(timezone.utc)).isoformat()
    return FeatureLogRecord(
        ts=ts,
        site_slug=site_slug,
        surface=surface,
        query=query,
        subject_entity_id=subject_entity_id,
        entity_type=entity_type,
        entity_id=entity_id,
        blend_score=blend_score,
        weights_source=weights_source,
        features=features.as_dict(),
    )


def log_feature_vector(record: FeatureLogRecord) -> str:
    """Emits one JSON line via the module logger and returns the exact
    line emitted (so tests/CLI callers can assert on it without needing
    a log-capture fixture)."""
    line = json.dumps(
        {
            "ts": record.ts,
            "site_slug": record.site_slug,
            "surface": record.surface,
            "query": record.query,
            "subject_entity_id": record.subject_entity_id,
            "entity_type": record.entity_type,
            "entity_id": record.entity_id,
            "blend_score": record.blend_score,
            "weights_source": record.weights_source,
            "features": record.features,
        },
        sort_keys=True,
    )
    logger.info(line)
    return line


def configure_jsonl_file_handler(path: str, *, level: int = logging.INFO) -> logging.Handler:
    """Convenience for local hand-checks/demos/tests: attach a plain file
    handler to this module's logger so feature-log lines land in a file
    a human (or a future ingestion job) can read. Not called by
    `reranker.py` itself -- production log routing is an ops decision
    outside this package's scope; this exists so `now-blender handcheck`
    and the test suite have somewhere concrete to point at."""
    handler = logging.FileHandler(path, encoding="utf-8")
    handler.setLevel(level)
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(handler)
    logger.setLevel(level)
    return handler
