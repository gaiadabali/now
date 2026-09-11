"""One-off cleanup for a bug introduced and fixed within this same F120
session: while diagnosing the routing/confidence work, `now-classifier
classify` was run several times against both live city DBs BEFORE
`confidence.py`'s location constants were corrected to their F113-measured
values (this session found F117's earlier promotion had only patched
*existing* rows via a one-time SQL backfill, not the classifier's own
code, so every re-run before the fix landed re-queued thousands of
already-resolved location facts back to `pending`, regressing F117's
"location pending is zero" invariant). The classifier fix itself
(confidence.py) stops this from happening on any FUTURE run, but does not
retroactively delete the stale `pending` rows this session's own earlier
runs already inserted -- this script does that, narrowly and verified.

Verified baseline: location pending was 0 in both cities before this
session's work began (F117, 2026-09-10). `vocabulary_misses=0` on the
post-fix re-run in both cities, so there is no legitimate remaining reason
for a `pending` location row to exist -- confirmed per-row below, not
assumed: a row is only deleted if `engine.entity_terms` already holds an
ACCEPTED fact (source<>'editor' or ='editor', either is fine -- an editor
decision would also make this pending row redundant) for the exact same
(article, proposed term). Any row that does NOT have a matching accepted
fact is left alone and reported for manual investigation instead of being
silently deleted.
"""
from __future__ import annotations

from now_db.settings import city_database_url
from now_platform_db.settings import platform_database_url
from sqlalchemy import create_engine, text

CITIES = {"jakarta": "now_jakarta", "bali": "now_bali"}


def main() -> None:
    eng_platform = create_engine(platform_database_url())
    with eng_platform.connect() as conn:
        term_rows = conn.execute(
            text("select t.id::text, f.key, t.slug from engine.terms t join engine.facets f on f.id = t.facet_id "
                 "where f.key = 'location'")
        ).fetchall()
    term_id_by_slug = {slug: tid for tid, _fkey, slug in term_rows}

    for city, db_ref in CITIES.items():
        eng = create_engine(city_database_url(db_ref))
        with eng.connect() as conn:
            pending = conn.execute(
                text("select cr.id, rel.articles_id, cr.proposed_value "
                     "from classification_reviews cr "
                     "join classification_reviews_rels rel on rel.parent_id = cr.id and rel.path = 'entity' "
                     "where cr.facet_key = 'location' and cr.review_state = 'pending'")
            ).fetchall()

        safe_to_delete = []
        unmatched = []
        with eng.connect() as conn:
            for review_id, article_id, proposed_value in pending:
                term_id = term_id_by_slug.get(proposed_value)
                if term_id is None:
                    unmatched.append((review_id, article_id, proposed_value, "no such term in vocabulary"))
                    continue
                has_fact = conn.execute(
                    text("select 1 from engine.entity_terms where entity_type='article' and entity_id=:eid "
                         "and term_id=cast(:tid as uuid)"),
                    {"eid": str(article_id), "tid": term_id},
                ).fetchone()
                if has_fact:
                    safe_to_delete.append(review_id)
                else:
                    unmatched.append((review_id, article_id, proposed_value, "no matching accepted fact in entity_terms"))

        print(f"{city}: {len(pending)} pending location reviews; {len(safe_to_delete)} verified redundant "
              f"(matching accepted fact exists), {len(unmatched)} NOT deleted (need investigation)")
        for row in unmatched[:20]:
            print("   UNMATCHED:", row)

        if safe_to_delete:
            with eng.begin() as conn:
                conn.execute(
                    text("delete from classification_reviews_rels where parent_id = any(:ids)"),
                    {"ids": safe_to_delete},
                )
                result = conn.execute(
                    text("delete from classification_reviews where id = any(:ids)"),
                    {"ids": safe_to_delete},
                )
                print(f"{city}: deleted {result.rowcount} redundant pending location review rows (+ their rels)")

        with eng.connect() as conn:
            remaining = conn.execute(
                text("select count(*) from classification_reviews where facet_key='location' and review_state='pending'")
            ).scalar()
        print(f"{city}: pending location reviews remaining: {remaining}")


if __name__ == "__main__":
    main()
