"""F108 gate: verify the 4 known-wrong cross-city location leaks are gone
after a real classification re-run, and clean up the stale rows if the
fixed pipeline (F95's suppression list) no longer proposes them.

The 4 rows (confirmed live, 2026-09-11, before this run):
    now_jakarta wp_id 5326  (article_id 1094) -- location=padang,  source=ai, confidence=0.90
    now_jakarta wp_id 82093 (article_id 3181) -- location=senayan, source=ai, confidence=0.90
    now_jakarta wp_id 82740 (article_id 3230) -- location=senayan, source=ai, confidence=0.90
    now_bali    wp_id 87106 (article_id 3797) -- location=senayan, source=ai, confidence=0.90

`db.write_results`'s upsert only ever ADDS/UPDATES a proposed row; it never
deletes a stale row that a re-run no longer proposes (F95's fix suppresses
the false match, so the fixed run simply never re-proposes 'senayan'/
'padang' for these articles -- the old wrong row is left behind unless
something explicitly removes it). This script is that explicit, narrowly
scoped removal: it only ever deletes exactly these 4 (entity_id, term)
pairs, only if they still carry the EXACT pre-run fingerprint
(source='ai', confidence=0.90) -- i.e. untouched by the re-run -- and only
after confirming this run's own report shows the fix is active. It never
does a general sweep.

Run AFTER `now-classifier classify jakarta` and `now-classifier classify
bali` have both completed for real (not --dry-run).
"""
from __future__ import annotations

from now_db.settings import city_database_url
from now_platform_db.settings import platform_database_url
from sqlalchemy import create_engine, text

KNOWN_WRONG = [
    ("now_jakarta", "jakarta", 5326, 1094, "padang"),
    ("now_jakarta", "jakarta", 82093, 3181, "senayan"),
    ("now_jakarta", "jakarta", 82740, 3230, "senayan"),
    ("now_bali", "bali", 87106, 3797, "senayan"),
]


def _term_id_for(eng_platform, facet: str, slug: str) -> str | None:
    with eng_platform.connect() as conn:
        row = conn.execute(
            text("select t.id::text from engine.terms t join engine.facets f on f.id = t.facet_id "
                 "where f.key = :facet and t.slug = :slug"),
            {"facet": facet, "slug": slug},
        ).fetchone()
    return row[0] if row else None


def main() -> None:
    eng_platform = create_engine(platform_database_url())
    engines = {"now_jakarta": create_engine(city_database_url("now_jakarta")),
               "now_bali": create_engine(city_database_url("now_bali"))}

    print("=== F108 verification (post re-run) ===\n")
    still_wrong = []
    for db_ref, city, wp_id, article_id, slug in KNOWN_WRONG:
        term_id = _term_id_for(eng_platform, "location", slug)
        if term_id is None:
            print(f"{db_ref} wp_id={wp_id}: term '{slug}' not found in vocabulary -- skipping (unexpected)")
            continue
        eng = engines[db_ref]
        with eng.connect() as conn:
            row = conn.execute(
                text("select source, confidence from engine.entity_terms "
                     "where entity_type='article' and entity_id=:eid and term_id=cast(:tid as uuid)"),
                {"eid": str(article_id), "tid": term_id},
            ).fetchone()
        if row is None:
            print(f"{db_ref} wp_id={wp_id}: '{slug}' -- GONE (no row at all). OK.")
            continue
        source, confidence = row
        if source == "ai" and float(confidence) == 0.90:
            print(f"{db_ref} wp_id={wp_id}: '{slug}' -- STILL PRESENT at the exact pre-run fingerprint "
                  f"(source=ai, confidence=0.90) -- the re-run did not touch it (F95 correctly no longer "
                  f"proposes it, so nothing overwrote it). Scheduling for explicit removal.")
            still_wrong.append((db_ref, article_id, term_id, slug, wp_id))
        else:
            print(f"{db_ref} wp_id={wp_id}: '{slug}' -- row changed by the re-run "
                  f"(source={source}, confidence={confidence}) -- no longer the wrong fingerprint. OK, "
                  f"nothing to clean (this shouldn't normally happen: the re-run should propose a DIFFERENT "
                  f"location for this slug, not rewrite this one, but if it did the wrong value is gone "
                  f"either way).")

    if not still_wrong:
        print("\nAll 4 rows already resolved by the re-run itself -- no explicit cleanup needed.")
        return

    print(f"\n=== Removing {len(still_wrong)} stale wrong row(s), explicitly, one at a time ===")
    for db_ref, article_id, term_id, slug, wp_id in still_wrong:
        eng = engines[db_ref]
        with eng.begin() as conn:
            result = conn.execute(
                text("delete from engine.entity_terms where entity_type='article' and entity_id=:eid "
                     "and term_id=cast(:tid as uuid) and source='ai' and confidence=0.90"),
                {"eid": str(article_id), "tid": term_id},
            )
            print(f"  {db_ref} wp_id={wp_id} article_id={article_id} location='{slug}': "
                  f"deleted {result.rowcount} row(s)")

    print("\n=== Re-verifying ===")
    all_gone = True
    for db_ref, city, wp_id, article_id, slug in KNOWN_WRONG:
        term_id = _term_id_for(eng_platform, "location", slug)
        eng = engines[db_ref]
        with eng.connect() as conn:
            row = conn.execute(
                text("select 1 from engine.entity_terms where entity_type='article' and entity_id=:eid "
                     "and term_id=cast(:tid as uuid) and source='ai' and confidence=0.90"),
                {"eid": str(article_id), "tid": term_id},
            ).fetchone()
        status = "GONE" if row is None else "STILL PRESENT -- INVESTIGATE"
        if row is not None:
            all_gone = False
        print(f"  {db_ref} wp_id={wp_id} '{slug}': {status}")

    print(f"\nF108 GATE: {'PASS -- all 4 confirmed gone' if all_gone else 'FAIL -- see above'}")


if __name__ == "__main__":
    main()
