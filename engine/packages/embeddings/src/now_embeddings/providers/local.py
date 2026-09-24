"""Real embedding provider -- local, CPU-only, no API key, no network
dependency after the one-time model download.

**Why local and not Ollama Cloud (the configured shared "brain")**: verified
directly, not assumed. `GET {OLLAMA_CLOUD_BASE_URL}/models` lists only chat
models (kimi-k2.7-code, glm-5.x, deepseek-v4-*, qwen3.5, ...) -- no
`nomic-embed-text`, no `mxbai-embed-large`, nothing embedding-shaped.
`POST {OLLAMA_CLOUD_BASE_URL}/embeddings` returns
`{"error":"path \"/v1/embeddings\" not found"}` for both an embedding-model
name and a chat-model name -- the cloud tier exposes no embeddings route at
all, full stop. See the package README "Provider investigation" for the
exact commands run.

**Why `fastembed` and not `sentence-transformers`**: both would work, but
`sentence-transformers` pulls in PyTorch, whose default PyPI wheel on
Windows without an explicit CPU index URL is the CUDA build (multi-GB
download) even on a machine with no GPU. `fastembed` runs the same class of
model through ONNX Runtime -- a ~15 MB CPU-only dependency, no CUDA, no
multi-GB download -- for identical output quality (it's the same
HuggingFace weights, exported to ONNX and int8-quantized).

**Why `BAAI/bge-small-en-v1.5` (384-dim) and not a bigger model**: measured,
not guessed. In this sandboxed dev environment `bge-base-en-v1.5` (768-dim)
took ~2-2.5s per ~1,200-character article text; `bge-small-en-v1.5`
(384-dim) took ~0.3-0.5s for the same text -- roughly 5x faster for a
well-regarded, widely-used small English embedding model (strong showing on
MTEB for its size class). At ~5,200 embeddable rows (articles + places +
terms) the difference is the entire backfill running in well under an hour
vs. several hours. Content is EN-only for v1 (ARCHITECTURE.md §18 decision
5), so an English-only model is the right choice, not a limitation.

**Why not multilingual-e5 or a long-context model (nomic-embed-text-v1.5,
8k tokens)**: no article in the archive needs more than the ~512-token
window every standard BERT-sized encoder gives (median article is ~4,800
characters -- see README "Truncation" for how this pipeline handles that
honestly), and a long-context model would cost meaningfully more compute
for a context window this pipeline doesn't need to fill.
"""

from __future__ import annotations

from now_embeddings.models import ModelSpec, active_spec, get_spec

# The live model, resolved once at import from `now_embeddings.models`
# (NOW_EMBEDDING_MODEL, else DEFAULT_MODEL). Kept as module constants
# because `now_search.query_embedder` and the CLI import them by these
# names; they are no longer literals, so they cannot drift from the config.
_ACTIVE = active_spec()
MODEL_NAME = _ACTIVE.name
DIM = _ACTIVE.dim

_registered_custom: set[str] = set()


def load_text_embedding(spec: ModelSpec, *, threads: int):
    """A `fastembed.TextEmbedding` for `spec`, registering it first if
    fastembed does not ship it (e5-small, bge-m3 -- see `models.REGISTRY`).
    Shared by this provider and `now_search.query_embedder`-style callers
    so a custom model is registered in exactly one way."""
    from fastembed import TextEmbedding

    if spec.custom is not None and spec.name not in _registered_custom:
        from fastembed.common.model_description import ModelSource, PoolingType

        known = {m["model"].lower() for m in TextEmbedding.list_supported_models()}
        if spec.name.lower() not in known:
            TextEmbedding.add_custom_model(
                model=spec.name,
                pooling=PoolingType[spec.custom.pooling],
                normalization=True,
                sources=ModelSource(hf=spec.custom.hf_repo),
                dim=spec.dim,
                model_file=spec.custom.model_file,
                additional_files=list(spec.custom.additional_files),
            )
        _registered_custom.add(spec.name)
    return TextEmbedding(model_name=spec.name, threads=threads)


class LocalProvider:
    """Lazy-loads the ONNX model on first construction (not at import time)
    so importing `now_embeddings` never pays the ~25s HuggingFace Hub /
    model-load cost, and so the offline provider + CLI help text stay fast
    even when this module is never actually used.

    `model=None` means the configured model (`now_embeddings.models`); an
    explicit name is for the WS6 comparison and the rollout backfill, which
    embed under a model that is not (yet) the live one."""

    def __init__(self, model: str | None = None, *, threads: int = 16) -> None:
        self.spec = get_spec(model) if model else _ACTIVE
        self.name = self.spec.name
        self.dim = self.spec.dim
        self._model = load_text_embedding(self.spec, threads=threads)

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        # The passage prefix is applied here, not in `textbuild`, so
        # `text_hash` stays a hash of the article's own text: switching model
        # must not by itself make every row look "changed" to the other
        # model's idempotency check.
        prefix = self.spec.passage_prefix
        inputs = [prefix + t for t in texts] if prefix else texts
        # fastembed returns L2-normalized vectors for every registered model
        # (built-in models by training, custom ones via `normalization=True`)
        # -- cosine similarity and dot product coincide, matching
        # `vector_cosine_ops` on the HNSW index. The HNSW query uses `<=>`
        # (cosine distance), which is correct regardless.
        return [vec.tolist() for vec in self._model.embed(inputs, batch_size=32)]

    def embed_queries(self, queries: list[str]) -> list[list[float]]:
        """Query-side counterpart (asymmetric models want a different
        marker on queries than on passages)."""
        if not queries:
            return []
        prefix = self.spec.query_prefix
        inputs = [prefix + q for q in queries] if prefix else queries
        return [vec.tolist() for vec in self._model.embed(inputs, batch_size=32)]
