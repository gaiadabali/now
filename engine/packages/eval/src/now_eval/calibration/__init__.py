"""F96/F97 confidence-mapping calibration.

Deliberately a separate corner of `now_eval` from the CI-gated harness
(`now_eval.datasets` / `now_eval.harness`): the harness is a pure function of
two version-controlled JSONL files and must stay reproducible byte-for-byte in
CI with no DB and no network. This subpackage is the opposite by necessity --
it reads the *live* classifier output straight out of `now_jakarta` /
`now_bali` (because ARCHITECTURE.md's own instruction is "do not re-run
classification": the confidence values already written to those DBs by
`now-classifier classify` earlier this wave are the object under study, not
something this package can regenerate from source) and it calls the shared
Ollama Cloud provider for blind proxy labels.

ARCHITECTURE.md §1 ("deterministic engine decides, LLM narrates") applies
here too: the LLM below is strictly a *labelling aid for this one-time
evaluation*, run once over a few hundred articles to produce ground truth to
measure the classifier against. It is never imported by, or reachable from,
any runtime request path -- `now_classifier` does not depend on this package
and never will.

Modules:
- `strata.py` / `stats.py`: pure logic (stratified sampling target sizes,
  Wilson score intervals, the two-stage accuracy estimator). No DB, no
  network -- unit-tested directly, always collectible even when the
  `calibration` extra isn't installed (CI's default `uv sync --extra dev`).
- `db_frame.py`: reads `now_jakarta` / `now_bali` (classifier output) and
  `now_platform` (vocabulary) plus the two cities' `articles.jsonl`. Needs
  the `calibration` extra (sqlalchemy/psycopg/now-db/now-platform-db).
- `llm_client.py`: blind Ollama Cloud proxy labelling. Needs `requests` and
  `OLLAMA_CLOUD_*` env vars -- never prints or logs the API key.
- `adjudication.py`: merges classifier + LLM proposals, selects the
  disagreement + control-agreement queue, renders the adjudication HTML.
- `mapping.py`: turns adjudicated accuracy-per-band into an evidence-based
  label->number mapping recommendation.
"""
