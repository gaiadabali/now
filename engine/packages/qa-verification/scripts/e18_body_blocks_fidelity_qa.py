"""Independent QA verification of E1.8's body_blocks fidelity claim.

Not the implementer's `now-loader verify` command (though it shares the
same `clean_article` reference transform, which IS the content-clean
package under test, not loader logic) -- this script:

  1. Picks its OWN random sample of legacy_wp_id's, drawn directly from
     the live `now_jakarta.public.articles` table via `ORDER BY random()`
     in psql (not the loader's `random.Random(seed=42)` over the JSONL,
     which is what `now-loader verify --seed 42` reuses by default).
  2. Loads the matching row from the E1.1 extraction JSONL
     (`jakarta/content/extracted/articles.jsonl`) by wp_id.
  3. Runs `now_content_clean.clean_article` on it fresh.
  4. Diffs the result against the stored `body_blocks` field-by-field
     (parsed JSON structural equality, not string equality -- jsonb
     reorders object keys).
  5. Reports exact block-level diffs for any mismatch.

Run from engine/packages/loader's venv (has now-content-clean + sqlalchemy
+ psycopg installed as editable deps):

    cd engine/packages/loader
    .venv/Scripts/python.exe ../qa-verification/scripts/e18_body_blocks_fidelity_qa.py \
        --input-dir ../../../jakarta/content/extracted \
        --wp-ids 344,190,1021,106395,6393,5217,52,6922,108294,88036,112301,92049,97884,86596,5832
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from now_content_clean import clean_article
from sqlalchemy import create_engine, text

DEFAULT_DSN = "postgresql+psycopg://now:now@localhost:15432/now_jakarta"


def iter_jsonl(path: Path):
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                yield json.loads(line)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input-dir", required=True, type=Path)
    ap.add_argument("--wp-ids", required=True, help="Comma-separated legacy_wp_id list, independently sampled.")
    ap.add_argument("--dsn", default=DEFAULT_DSN)
    args = ap.parse_args()

    wanted = {int(x.strip()) for x in args.wp_ids.split(",") if x.strip()}
    articles_by_wp_id = {}
    for article in iter_jsonl(args.input_dir / "articles.jsonl"):
        if article["wp_id"] in wanted:
            articles_by_wp_id[article["wp_id"]] = article

    engine = create_engine(args.dsn)
    mismatches = []
    checked = 0
    results = []

    with engine.connect() as conn:
        for wp_id in sorted(wanted):
            article = articles_by_wp_id.get(wp_id)
            if article is None:
                mismatches.append((wp_id, "NOT FOUND in articles.jsonl (sample id invalid)"))
                continue

            row = conn.execute(
                text('SELECT body_blocks FROM "public"."articles" WHERE legacy_wp_id = :wp_id'),
                {"wp_id": wp_id},
            ).fetchone()
            if row is None:
                mismatches.append((wp_id, "NOT FOUND in DB (legacy_wp_id missing)"))
                continue

            stored_blocks = row[0]
            expected_blocks = clean_article(article).blocks
            # Normalize both sides through json dump/load to guarantee
            # pure structural comparison (defends against any exotic
            # non-JSON-native types clean_article might return, e.g. tuples).
            stored_norm = json.loads(json.dumps(stored_blocks, ensure_ascii=False))
            expected_norm = json.loads(json.dumps(expected_blocks, ensure_ascii=False))
            checked += 1

            if stored_norm != expected_norm:
                # find first differing block index for a useful repro
                diff_at = None
                for i in range(max(len(stored_norm), len(expected_norm))):
                    s = stored_norm[i] if i < len(stored_norm) else "<missing>"
                    e = expected_norm[i] if i < len(expected_norm) else "<missing>"
                    if s != e:
                        diff_at = (i, s, e)
                        break
                mismatches.append((wp_id, f"body_blocks differ; len stored={len(stored_norm)} expected={len(expected_norm)}; first diff at block {diff_at}"))
            else:
                results.append((wp_id, len(stored_norm)))

    print(f"[qa] independently sampled wp_ids: {sorted(wanted)}")
    print(f"[qa] checked={checked}/{len(wanted)} mismatches={len(mismatches)}")
    for wp_id, blocks in results:
        print(f"  OK  wp_id={wp_id} blocks={blocks}")
    for wp_id, reason in mismatches:
        print(f"  FAIL wp_id={wp_id}: {reason}")

    return 1 if mismatches else 0


if __name__ == "__main__":
    sys.exit(main())
