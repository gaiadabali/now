"""Embeds a search query string with the exact same *model* that produced
`engine.embeddings` (`BAAI/bge-small-en-v1.5`, 384-dim). Embedding the
query with a different model than the corpus would make cosine
similarity meaningless, so `MODEL_NAME`/`DIM` are imported from
`now_embeddings.providers.local` -- the single source of truth for which
model that is -- rather than re-declared here where they could drift.

**Why this module builds its own `fastembed.TextEmbedding` instead of
reusing `now_embeddings.providers.local.LocalProvider` directly**:
measured, not assumed. `LocalProvider` hardcodes `threads=16`, tuned for
*batch* embedding (backfilling ~5,200 rows -- see that module's
docstring). For a live *single-query* embed on the p95 path, 16 ONNX
intra-op threads on this 16-core machine is thread-management overhead
with nothing to parallelise (batch size 1):

    threads=16:  p50=94.0ms  p95=125.6ms   (measured, fastembed 0.8.0)
    threads=4:   p50=46.5ms  p95=52.4ms

That is the difference between meeting and missing this ticket's p95 <
80ms criterion on the embedding step alone, before lexical/semantic SQL
or RRF even run. `THREADS` below is `4` for exactly this reason. The
embedding *values* are identical either way (ONNX Runtime intra-op
thread count is a scheduling detail, not a numerical one) -- only
latency changes, so this does not risk any drift from the corpus
vectors' provenance.

**F60 -- the number above is superseded, and the lesson is "pin your
inference runtime".** The `threads=4` p50/p95 pair above did not record
which `onnxruntime` version it was measured against -- `onnxruntime` had
no version pin anywhere in this repo, only a transitive pull-in via
`fastembed`. That silently drifted this environment to `onnxruntime
1.29.0` at some point, and single-query CPU inference on *this exact
model/thread config* regressed to **p50 ~99-112ms / p95 ~117-126ms** --
worse than the `threads=16` row above, on the *same* `threads=4` code
path, with zero change in this file. Root-caused by re-testing across
onnxruntime releases with everything else held constant (see this
package's `BENCHMARK.md`, "F60" section, for the full table): every
version from 1.19.2 through 1.25.1 measured **p50 ~5.5-27ms**, `1.29.0`
alone measured ~100ms, at comparable-or-worse host load. `pyproject.toml`
now pins `onnxruntime>=1.21.0,<1.25,!=1.24.0,!=1.24.1` (resolved to
`1.24.4`) for exactly this reason -- re-benchmark before moving that
ceiling. Cite `BENCHMARK.md`'s numbers going forward, not the pair
above; they are kept here only as the historical reason `threads=4` was
chosen, not as a current performance claim.

Lazy singleton: the ONNX model load itself is a one-time ~1s-scale cost,
paid once in `warm_up()` (or on first `embed_query()` call) and
amortised across every subsequent query in a process -- never on the
per-query p95 path.
"""

from __future__ import annotations

from now_embeddings.models import get_spec
from now_embeddings.providers.local import DIM, MODEL_NAME, load_text_embedding

THREADS = 4

# WS6: MODEL_NAME follows the one config point (`now_embeddings.models`,
# NOW_EMBEDDING_MODEL). The spec supplies what a non-default model needs
# on the query side -- a fastembed registration for models fastembed does
# not ship, and the query marker asymmetric models (e5) were trained with.
# For the default model both are no-ops, so its query vectors are
# unchanged by this indirection.
_SPEC = get_spec(MODEL_NAME)

_model = None


def model_name() -> str:
    return MODEL_NAME


def model_dim() -> int:
    return DIM


def _get_model():
    global _model
    if _model is None:
        _model = load_text_embedding(_SPEC, threads=THREADS)
    return _model


def embed_query(query: str) -> list[float]:
    return next(iter(_get_model().embed([_SPEC.query_prefix + query]))).tolist()


def warm_up() -> None:
    """Force the lazy model load now, outside of any latency measurement.

    Idempotent at module scope: `_model` is a process-wide singleton, so
    once any caller has loaded it there is nothing left to force and this
    returns without embedding anything. That matters on the request path
    -- `SearchEngine._warmed_up` is *instance* state, so a per-request
    engine (as `app.domain.search.service` builds) calls this on every
    single request. Without the guard each of those would pay a real
    `embed_query("warm up")` (~5-27ms, BENCHMARK.md F60) purely to
    re-discover an already-loaded model, on the p95 path this package's
    whole design is trying to protect."""
    if _model is not None:
        return
    embed_query("warm up")
