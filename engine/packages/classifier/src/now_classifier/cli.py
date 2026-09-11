from __future__ import annotations

from pathlib import Path

import click
from now_taxonomy_evidence.features import compute_features
from now_taxonomy_evidence.sources import find_repo_root, load_articles, load_categories, load_seed
from now_taxonomy_evidence.text import build_location_matcher, match_locations
from now_taxonomy_evidence.vectors import load_embeddings

from .db import fetch_id_by_wp_id, make_engine, write_results
from .embed_routing import load_centroid_models
from .report import write_report
from .resolve import classify_article
from .review_doc import load_review_doc, resolve_all_category_fixed_locations, resolve_article_category
from .vocabulary import load_term_index

CITY_DB = {"jakarta": "now_jakarta", "bali": "now_bali"}


@click.group()
def cli() -> None:
    pass


@cli.command("classify")
@click.argument("city", type=click.Choice(["jakarta", "bali"]))
@click.option("--dry-run", is_flag=True, help="Compute everything, print stats, write nothing to the DB.")
@click.option("--limit", type=int, default=None, help="Only process the first N articles (debugging).")
def classify_cmd(city: str, dry_run: bool, limit: int | None) -> None:
    root = find_repo_root()
    click.echo(f"[{city}] loading articles + categories + taxonomy-review.json ...")
    articles = load_articles(city, root)
    if limit:
        articles = articles[:limit]
    categories_by_name = load_categories(city, articles, root)
    review = load_review_doc(city, root)

    click.echo(f"[{city}] computing per-article cue features ({len(articles)} articles; cached on disk) ...")
    seed = load_seed(root)
    # `--limit` truncates the article list for debugging; never let a partial
    # run overwrite the full-corpus on-disk feature cache (compute_features's
    # cache key is per-city, not per-subset).
    features = compute_features(city, articles, seed=seed, use_cache=(limit is None))

    # `now_taxonomy_evidence.features` reports one combined title+lead location
    # match per article -- fine for the evidence pack's aggregate cluster
    # stats, but not safe to auto-apply as fact per-article: a live check on
    # this corpus (wp_id 5557, "siomay bandung" / "nasi bali" as DISH names in
    # a hotel promo's lead paragraph) showed the lead zone produces real false
    # positives that the title zone does not. So this package re-derives
    # title-only vs lead-only hits itself: a title hit is high-trust (a
    # location name in the headline is a deliberate editorial signal), a
    # lead-only hit is downgraded and routed to the review queue instead of
    # auto-applied.
    matcher = build_location_matcher(seed["terms"]["location"])
    loc_hints: dict[int, tuple[list[str], list[str]]] = {}
    for a in articles:
        title_hits = match_locations(a.title, "", matcher)
        lead_hits = match_locations("", a.text[:400], matcher)
        lead_only = [s for s in lead_hits if s not in title_hits]
        loc_hints[a.wp_id] = (title_hits, lead_only)

    click.echo(f"[{city}] loading platform vocabulary (engine.terms) ...")
    terms = load_term_index()

    # F120 routing: `category_fixed_{high,medium}`/`cue_{confident,fired}`
    # type/format bands route to a keyword-cue or embeddings-centroid
    # instrument per PROGRESS.md's measured decision. The centroid model is
    # a version-controlled artifact (built offline from the same 253-item
    # human-adjudicated ground truth F118/F120 measured against -- see
    # `embed_routing.load_centroid_models`); article vectors come from this
    # city's own `engine.embeddings` (already backfilled, E2.4/E2.4b).
    # Missing either degrades to abstain-and-review for the affected
    # articles/bands (see `embed_routing.route`), never a crash.
    centroid_models = load_centroid_models()
    if not centroid_models:
        click.echo(f"[{city}] WARNING: no F120 routing centroid artifact found -- "
                    f"cue_confident/cue_fired bands will abstain to review this run.")
    vec_space = load_embeddings(city)
    vector_by_wp_id: dict[int, list[float]] = {}
    if vec_space is not None and vec_space.matrix.size:
        idx = vec_space.index()
        vector_by_wp_id = {wp: vec_space.matrix[i].tolist() for wp, i in idx.items()}
    else:
        click.echo(f"[{city}] WARNING: no article embeddings available -- "
                    f"cue_confident/cue_fired bands will abstain to review this run.")

    click.echo(f"[{city}] classifying ...")
    results = []
    for a in articles:
        d10 = resolve_article_category(a, categories_by_name, review)
        # F104: `location` is multi-cardinality, so every co-filed category's
        # own fixed location must be considered, not just the one D10 chose
        # to drive type/subtype/format -- see resolve_all_category_fixed_locations.
        category_locs = resolve_all_category_fixed_locations(a, categories_by_name, review)
        title_hits, lead_only_hits = loc_hints[a.wp_id]
        article_vector = vector_by_wp_id.get(a.wp_id)
        results.append(classify_article(a, d10, features[a.wp_id], terms, title_hits, lead_only_hits,
                                         category_locs, article_vector, centroid_models))

    click.echo(f"[{city}] connecting to {CITY_DB[city]} ...")
    engine = make_engine(CITY_DB[city])
    id_by_wp_id = fetch_id_by_wp_id(engine)
    missing = [r.wp_id for r in results if r.wp_id not in id_by_wp_id]
    if missing:
        click.echo(f"[{city}] WARNING: {len(missing)} classified wp_ids have no matching public.articles row "
                   f"(not loaded yet, or legacy_wp_id mismatch) -- skipped: {missing[:10]}{'...' if len(missing) > 10 else ''}")

    stats = write_results(engine, id_by_wp_id, results, terms, site_slug=city, dry_run=dry_run)

    report_path = root / city / "site" / "e2.1-classification-report.md"
    write_report(report_path, city, results, stats)
    click.echo(f"[{city}] report written to {report_path}")
    click.echo(f"[{city}] type accepted={stats.type_accepted} reviewed={stats.type_reviewed}")
    click.echo(f"[{city}] format accepted={stats.format_accepted} reviewed={stats.format_reviewed}")
    click.echo(f"[{city}] subtype accepted={stats.subtype_accepted} reviewed={stats.subtype_reviewed}")
    click.echo(f"[{city}] location accepted={stats.location_accepted} reviewed={stats.location_reviewed}")
    click.echo(f"[{city}] vocabulary misses={stats.vocabulary_misses}")
    click.echo(f"[{city}] stale facet terms removed={stats.stale_facet_terms_removed}")
    click.echo(f"[{city}] F132 articles<->entity_terms synced={stats.articles_facets_synced} "
               f"drift skipped={stats.articles_facet_drift_skipped}")
    if dry_run:
        click.echo(f"[{city}] DRY RUN -- nothing written to the database.")


@cli.command("check-bali-embeddings")
def check_bali_embeddings() -> None:
    from now_db.settings import city_database_url
    from sqlalchemy import create_engine, text

    eng = create_engine(city_database_url("now_bali"))
    with eng.connect() as conn:
        n = conn.execute(text("select count(*) from engine.embeddings where entity_type='article'")).scalar()
        total = conn.execute(text("select count(*) from public.articles")).scalar()
    click.echo(f"now_bali.engine.embeddings (article rows): {n} / {total} articles ({100.0*n/total:.1f}%)")


if __name__ == "__main__":
    cli()
