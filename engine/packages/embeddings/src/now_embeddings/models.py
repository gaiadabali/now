"""Which embedding model the engine uses -- the one place that decides it.

Every reader of `engine.embeddings` has to agree on one `model` value:
a query vector compared against rows written by a different model is
meaningless, and the table is keyed by `model` precisely so more than one
can coexist (README, "Notes for E3.1"). Before WS6 that value was a
literal copied into each reader -- the backfill, the worker, search's
query embedder, the classifier's vector loader, the web tier's Read Next
query -- and nothing made them agree except care.

Now:

* `REGISTRY` lists every model this package knows how to run, with what
  each one needs (dimension, query/passage prefixes, how fastembed loads
  it). A model not in the registry cannot be activated by accident.
* `active_model_name()` is the answer to "which one is live": the
  `NOW_EMBEDDING_MODEL` env var if set, else `DEFAULT_MODEL`. Python
  readers call it (directly, or via `providers.local.MODEL_NAME`); the web
  tier reads the same env var in `apps/web/src/lib/embeddingModel.ts`,
  whose fallback literal is pinned equal to `DEFAULT_MODEL` by
  `tests/test_models.py` -- a mismatch fails this package's suite.

Switching model is therefore a config change, and rolling back is the
same change reversed: rows are keyed by model, so the old model's rows
are never touched by a backfill under the new one (see
`scripts/rollout_embedding_model.py` for the order to do it in).

WS6 measured whether a stronger or multilingual model is worth switching
to (docs/EDITION-2-PLAN.md, "WS6 -- Embeddings"); the candidates it
compared are registered here so the measurement is reproducible, but
`DEFAULT_MODEL` stays whatever that write-up decided.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

ENV_VAR = "NOW_EMBEDDING_MODEL"
DEFAULT_MODEL = "BAAI/bge-small-en-v1.5"

# `engine.embeddings.vec` is `vector(384)` (migration 0004). A model of any
# other width can be *measured* (the comparison script keeps its vectors in
# local files) but cannot be *stored* until a migration adds somewhere to
# put it -- `storable` below is what the backfill and the worker check.
STORED_DIM = 384


@dataclass(frozen=True)
class CustomOnnxSource:
    """For a model fastembed does not ship: where its ONNX export lives on
    the HF Hub and how its output is pooled. Registered with
    `TextEmbedding.add_custom_model` the first time it is loaded."""

    hf_repo: str
    pooling: str  # "MEAN" | "CLS"
    model_file: str = "onnx/model.onnx"
    additional_files: tuple[str, ...] = ()


@dataclass(frozen=True)
class ModelSpec:
    name: str  # stored verbatim in engine.embeddings.model
    dim: int
    languages: str  # "en" | "multilingual" -- documentation, not behaviour
    max_tokens: int
    # e5-family models are trained with these markers and measurably worse
    # without them; bge v1.5 needs neither for passages and the pipeline has
    # never used its optional query instruction, so both stay empty for it
    # (changing that would change every stored bge-small vector).
    query_prefix: str = ""
    passage_prefix: str = ""
    custom: CustomOnnxSource | None = None

    @property
    def storable(self) -> bool:
        return self.dim == STORED_DIM


REGISTRY: dict[str, ModelSpec] = {
    spec.name: spec
    for spec in (
        ModelSpec(name="BAAI/bge-small-en-v1.5", dim=384, languages="en", max_tokens=512),
        ModelSpec(name="BAAI/bge-base-en-v1.5", dim=768, languages="en", max_tokens=512),
        ModelSpec(
            name="intfloat/multilingual-e5-small",
            dim=384,
            languages="multilingual",
            max_tokens=512,
            query_prefix="query: ",
            passage_prefix="passage: ",
            custom=CustomOnnxSource(hf_repo="intfloat/multilingual-e5-small", pooling="MEAN"),
        ),
        ModelSpec(
            name="BAAI/bge-m3",
            dim=1024,
            languages="multilingual",
            max_tokens=8192,
            custom=CustomOnnxSource(
                hf_repo="BAAI/bge-m3",
                pooling="CLS",
                additional_files=("onnx/model.onnx_data", "onnx/Constant_7_attr__value"),
            ),
        ),
    )
}


class UnknownEmbeddingModel(ValueError):
    pass


def get_spec(name: str) -> ModelSpec:
    try:
        return REGISTRY[name]
    except KeyError:
        raise UnknownEmbeddingModel(
            f"embedding model {name!r} is not registered in now_embeddings.models.REGISTRY "
            f"(known: {', '.join(sorted(REGISTRY))})"
        ) from None


def active_model_name() -> str:
    """`NOW_EMBEDDING_MODEL` if set (and registered), else `DEFAULT_MODEL`.
    Read per call rather than cached, so a test or a one-off CLI run can set
    the env var without reloading modules; long-lived processes resolve it
    once at construction (see `providers.local.LocalProvider`)."""
    name = os.environ.get(ENV_VAR, "").strip() or DEFAULT_MODEL
    get_spec(name)  # fail loudly on a typo rather than query an empty model
    return name


def active_spec() -> ModelSpec:
    return get_spec(active_model_name())
