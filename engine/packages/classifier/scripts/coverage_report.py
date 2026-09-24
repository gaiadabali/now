"""WS5: before/after facet coverage per city, and picker-combination
match counts. Read-only; safe to run any time. Not part of the installed
CLI -- a one-off reporting tool, like `build_calibration_sample.py`."""
from __future__ import annotations

from now_classifier.vocabulary import load_term_index
from now_db.settings import city_database_url
from sqlalchemy import create_engine, text

CITIES = {"jakarta": "now_jakarta", "bali": "now_bali"}
FACETS = ["topic", "audience", "vibe", "cuisine", "price_band", "occasion"]


def main() -> None:
    terms = load_term_index()
    facet_term_ids = {f: [uid for uid, _p in terms.by_facet.get(f, {}).values()] for f in FACETS}
    slug_to_id = {f: {slug: uid for slug, (uid, _p) in terms.by_facet.get(f, {}).items()} for f in FACETS}

    for city, db in CITIES.items():
        eng = create_engine(city_database_url(db))
        with eng.connect() as conn:
            total_published = conn.execute(text("select count(*) from public.articles where _status='published'")).scalar_one()
            print(f"\n=== {city} ({db}) -- {total_published} published articles ===")
            for f in FACETS:
                ids = facet_term_ids[f]
                if not ids:
                    continue
                n_articles = conn.execute(
                    text("select count(distinct entity_id) from engine.entity_terms "
                         "where entity_type='article' and term_id = any(cast(:ids as uuid[]))"),
                    {"ids": ids},
                ).scalar_one()
                n_rows = conn.execute(
                    text("select count(*) from engine.entity_terms "
                         "where entity_type='article' and term_id = any(cast(:ids as uuid[]))"),
                    {"ids": ids},
                ).scalar_one()
                pct = 100.0 * n_articles / total_published if total_published else 0.0
                print(f"  {f:12s} articles_tagged={n_articles:5d} ({pct:5.1f}%)  rows={n_rows}")

            # Picker-realistic combinations (engine/apps/web/src/lib/preferences.ts):
            # topics = topic facet; personas = audience, restricted to
            # PERSONA_SLUGS ['expat','local','tourist','business-traveller'];
            # budgets = price_band.
            print("  -- picker combination matches --")
            combos = [
                ("topics: sustainability OR food-drink", "topic", ["sustainability", "food-drink"], "any"),
                ("personas: tourist", "audience", ["tourist"], "any"),
                ("budgets: luxury", "price_band", ["luxury"], "any"),
            ]
            for label, facet, slugs, _mode in combos:
                ids = [slug_to_id[facet][s] for s in slugs if s in slug_to_id[facet]]
                if not ids:
                    print(f"  {label}: (no matching term ids)")
                    continue
                n = conn.execute(
                    text("select count(distinct a.id) from public.articles a "
                         "join engine.entity_terms et on et.entity_type='article' and et.entity_id = a.id::text "
                         "where a._status='published' and et.term_id = any(cast(:ids as uuid[]))"),
                    {"ids": ids},
                ).scalar_one()
                print(f"  {label}: {n} published articles now match")
        eng.dispose()


if __name__ == "__main__":
    main()
