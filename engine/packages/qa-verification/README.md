# QA verification — Waves 1-3 independent audit

Independent re-verification of five self-reported claims from Waves 1-3,
run against the real local stack (`docker-compose.yml`, Postgres on
`15432`, Redis on `16379`). No product code was modified. See the parent
conversation / report for the full per-claim verdicts; this directory
holds the reusable scripts and evidence.

## Contents

- `scripts/e12_independent_loss.py` — from-scratch (BeautifulSoup-based,
  not importing `now_content_clean.metrics`) re-implementation of the
  E1.2 content-loss measurement, run over all 4,772 articles plus a
  word-multiset diff to separate genuine content loss from
  whitespace-boundary tokenization noise.
- `scripts/e12_br_figcaption_bug.py` — minimal, isolated regression repro
  for the `<br>`-in-`<figcaption>` word-merge defect found during this
  audit (`now-content-clean` drops a bare `<br>` without inserting a
  word boundary, corrupting output text — see the audit report for
  scope: 28 bare occurrences across the corpus). Currently FAILs against
  `now_content_clean` as shipped.
- `evidence/e12_report_reproduced.json` — output of
  `now-content-clean clean` run by this audit over the full
  `jakarta/content/extracted/articles.jsonl`, reproducing the package's
  own claimed 0.000%/0.000%/1.207% median/p95/max.
- `evidence/e12_independent_result.json` — output of the independent
  BeautifulSoup-based measurement above (summary stats + full list of
  nonzero-loss and >10k-char-with-loss articles).

## Reproducing

```bash
# their own metric, for comparison
cd engine/packages/content-clean
PYTHONPATH=src python -m now_content_clean.cli clean \
  ../../../jakarta/content/extracted/articles.jsonl \
  -o /tmp/blocks.jsonl --report /tmp/report.json

# independent cross-check
python engine/packages/qa-verification/scripts/e12_independent_loss.py \
  jakarta/content/extracted/articles.jsonl /tmp/blocks.jsonl /tmp/independent.json

# isolated bug repro (no full corpus needed)
PYTHONPATH=engine/packages/content-clean/src \
  python engine/packages/qa-verification/scripts/e12_br_figcaption_bug.py
```
