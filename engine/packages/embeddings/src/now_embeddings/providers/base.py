"""Provider interface (ARCHITECTURE.md §10: "cheap model for batch tagging
and embeddings"). `pipeline.py` calls this interface only, never a concrete
provider directly -- `OfflineProvider` and `LocalProvider` are
interchangeable, and a future API-backed provider (should a real key ever
show up -- see README "Provider investigation") plugs in the same way with
no change to the pipeline or the CLI beyond a new `--provider` choice.

One operation: `embed_batch`. There is no `embed_one` -- every provider is
expected to batch internally (the whole point of a batch-oriented backfill
over ~5,200 rows), so a `for text in texts: embed_one(text)` shim in the
pipeline would silently defeat that.

`dim` is a property of the provider, not a parameter to `embed_batch` --
pgvector's `engine.embeddings.vec` column is a single fixed dimension
(migration 0004), so a provider that returns vectors of a different length
than its own declared `dim` is a bug, not a valid variant.
"""

from __future__ import annotations

from typing import Protocol


class EmbeddingProvider(Protocol):
    name: str  # stored verbatim in engine.embeddings.model
    dim: int   # must match len(vec) for every vector this provider returns

    def embed_batch(self, texts: list[str]) -> list[list[float]]: ...
