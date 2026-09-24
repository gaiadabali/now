/**
 * Which `engine.embeddings.model` the web tier's semantic rails read.
 *
 * The web tier cannot import the Python registry that owns this decision
 * (`engine/packages/embeddings/src/now_embeddings/models.py`), so it reads
 * the same env var every engine process reads, `NOW_EMBEDDING_MODEL`, and
 * falls back to the same default. The fallback literal below is the only
 * copy of the model name in this app, and it is pinned equal to the
 * Python `DEFAULT_MODEL` by `engine/packages/embeddings/tests/test_models.py`
 * — change one without the other and that suite fails.
 *
 * Switching model (or rolling back) is therefore a config change made in
 * the same place for web, worker, search and classifier — after the new
 * model's rows exist (`scripts/rollout_embedding_model.py` in that
 * package). Rows are keyed by model, so the old model's rows stay put and
 * pointing back at them is the whole of a rollback.
 */
export const EMBEDDING_MODEL: string = process.env.NOW_EMBEDDING_MODEL?.trim() || 'BAAI/bge-small-en-v1.5'
