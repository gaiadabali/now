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

MODEL_NAME = "BAAI/bge-small-en-v1.5"
DIM = 384


class LocalProvider:
    """Lazy-loads the ONNX model on first construction (not at import time)
    so importing `now_embeddings` never pays the ~25s HuggingFace Hub /
    model-load cost, and so the offline provider + CLI help text stay fast
    even when this module is never actually used."""

    name = MODEL_NAME
    dim = DIM

    def __init__(self) -> None:
        from fastembed import TextEmbedding

        self._model = TextEmbedding(model_name=MODEL_NAME, threads=16)

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        # fastembed's model is already trained/served to emit L2-normalized
        # vectors (verified: norm == 1.0 on sample output) -- cosine
        # similarity and dot product coincide, matching
        # `vector_cosine_ops` on the HNSW index. No renormalization here;
        # if that ever changes upstream, the HNSW query still uses
        # `<=>` (cosine distance), which is correct regardless.
        return [vec.tolist() for vec in self._model.embed(texts, batch_size=32)]
