"""Offline / deterministic provider -- no network, no model download, no
API key, fully reproducible. Exists so the pipeline (fetch -> hash -> embed
-> upsert -> HNSW query), the CLI, and the Redis-driven re-embed worker can
all be exercised and unit-tested in CI with zero external dependencies,
mirroring `now_geocode.providers.offline`'s role for the same reason.

**This provider's output carries no semantic meaning whatsoever.** It is a
seeded pseudo-random unit vector derived from a sha256 hash of the input
text -- two different texts get uncorrelated vectors; the *same* text
always gets the *same* vector (determinism is the entire point: it lets a
test assert `embed(x) == embed(x)` and "re-running changes nothing"
without a model in the loop). Nearest-neighbour results computed from it
are meaningless and must never be presented as a real recommender. The
task's real deliverable (a working semantic recommender) is `local.py`;
this module is test/CI scaffolding only. `model="offline-deterministic-v1"`
makes any row written by this provider unmistakable in
`engine.embeddings.model` -- it can never be confused with a real
`BAAI/bge-small-en-v1.5` row because they share no primary key (model is
part of the PK) and the string itself says what it is.
"""

from __future__ import annotations

import hashlib
import math

DIM = 384  # matches engine.embeddings.vec's fixed column width (migration 0004)
MODEL_NAME = "offline-deterministic-v1"


def _seeded_unit_vector(text: str, dim: int) -> list[float]:
    # Expand a sha256 digest with a counter-based stream (digest of
    # "<hash>:<i>" for each needed 8-byte chunk) so `dim` can exceed the
    # digest's native 32 bytes without repeating the same bytes.
    values: list[float] = []
    base = hashlib.sha256(text.encode("utf-8")).digest()
    i = 0
    while len(values) < dim:
        chunk = hashlib.sha256(base + i.to_bytes(4, "big")).digest()
        for j in range(0, len(chunk), 4):
            if len(values) >= dim:
                break
            # Map 4 bytes -> a float in [-1, 1), deterministic, no external RNG.
            u = int.from_bytes(chunk[j : j + 4], "big") / 2**32
            values.append(u * 2 - 1)
        i += 1
    norm = math.sqrt(sum(v * v for v in values)) or 1.0
    return [v / norm for v in values]


class OfflineProvider:
    name = MODEL_NAME
    dim = DIM

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return [_seeded_unit_vector(t, self.dim) for t in texts]
