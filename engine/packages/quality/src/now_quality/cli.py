"""`now-quality score --url now_jakarta --articles-jsonl <path>`
`now-quality series --url now_jakarta --articles-jsonl <path> [--apply]`

See package README and each module's docstring for design rationale.
"""

from __future__ import annotations

import json
from pathlib import Path

import click

from now_quality import db, popularity, source
from now_quality.report import render_score_report, render_series_report
from now_quality.scoring import DEFAULT_WEIGHTS, QUALITY_FLOOR, STUB_CHAR_THRESHOLD, compute_quality
from now_quality.series import ArticleRow, cluster_titles, find_fuzzy_candidates, pick_current
from now_quality.textextract import article_text_stats


@click.group()
def cli() -> None:
    """now-quality: E2.6 quality scoring + series clustering."""


@cli.command("score")
@click.option("--url", required=True, help="City db_ref (e.g. now_jakarta) or full DSN.")
@click.option(
    "--articles-jsonl", required=True, type=click.Path(exists=True, path_type=Path),
    help="jakarta/content/extracted/articles.jsonl -- source of Yoast fields + view counts.",
)
@click.option("--popularity-head", default=popularity.DEFAULT_HEAD_N, show_default=True,
              help="How many top-viewed articles count as the real-signal head; the rest are zeroed as bot noise.")
@click.option("--floor", default=QUALITY_FLOOR, show_default=True, help="Quality floor reference value, for the report only.")
@click.option("--report", "report_path", type=click.Path(path_type=Path), default=None,
              help="Markdown report path (default: <db_ref>_quality_report.md next to cwd).")
@click.option("--dry-run", is_flag=True, help="Compute and report, but do not write to engine.quality_scores.")
def score(url: str, articles_jsonl: Path, popularity_head: int, floor: float, report_path: Path | None, dry_run: bool) -> None:
    engine = db.make_engine(url)
    articles = db.fetch_articles(engine)
    meta_by_wp_id = source.load_source_meta(articles_jsonl)

    views_by_wp_id = {wp_id: m.views for wp_id, m in meta_by_wp_id.items() if m.views is not None}
    priors = popularity.compute_priors(views_by_wp_id, head_n=popularity_head)

    # Series info (if `series` has already run) is folded into components so
    # the Engine Inspector (E3.4) can show it alongside quality without a
    # second table. Current-member is recomputed fresh from the live
    # `series_key` + titles/dates on every run -- it doesn't depend on
    # `series` having run first or in any particular order.
    by_series_key: dict[str, list] = {}
    for a in articles:
        if a.series_key:
            by_series_key.setdefault(a.series_key, []).append(a)
    current_id_by_series_key: dict[str, int] = {}
    for key, members in by_series_key.items():
        rows = [ArticleRow(id=m.id, title=m.title, published_at=m.published_at) for m in members]
        current_id_by_series_key[key] = pick_current(rows).id

    rows_to_write = []
    all_scores: list[float] = []
    stubs: list[tuple[int, str, int, float]] = []

    for a in articles:
        stats = article_text_stats(a.body_blocks)
        meta = meta_by_wp_id.get(a.legacy_wp_id) if a.legacy_wp_id is not None else None
        result = compute_quality(
            stats=stats,
            author_id=a.author_id,
            hero_media_id=a.hero_media_id,
            has_focuskw=meta.has_focuskw if meta else False,
            has_metadesc=meta.has_metadesc if meta else False,
            has_primary_category=meta.has_primary_category if meta else False,
        )
        all_scores.append(result.score)
        if stats.chars < STUB_CHAR_THRESHOLD:
            stubs.append((a.id, a.title, stats.chars, result.score))

        prior = priors.get(a.legacy_wp_id) if a.legacy_wp_id is not None else None
        components = dict(result.components)
        components["popularity"] = prior.as_components() if prior else {
            "views": None, "in_head": False, "prior_score": 0.0, "discarded_as_bot_noise": True,
            "note": "no legacy_wp_id / no view count in source jsonl",
        }
        components["series"] = {
            "series_key": a.series_key,
            "is_current": (current_id_by_series_key.get(a.series_key) == a.id) if a.series_key else None,
        }

        rows_to_write.append(
            {
                # F33 (migration 0005): engine.quality_scores.entity_id is
                # `text` holding the native public.articles.id PK verbatim
                # -- no uuid derivation. A plain `entity_id::int =
                # articles.id` join works with no hash math anywhere.
                "entity_type": "article",
                "entity_id": str(a.id),
                "score": result.score,
                "components_json": json.dumps(components),
            }
        )

    if not dry_run:
        db.upsert_quality_scores_bulk(engine, rows_to_write)

    report_path = report_path or Path(f"{url}_quality_report.md")
    report_path.write_text(
        render_score_report(
            n_articles=len(articles),
            scores=all_scores,
            stubs=sorted(stubs, key=lambda s: s[2]),
            floor=floor,
            head_n=popularity_head,
            head_min_views=next(iter(priors.values())).head_min_views if priors else 0,
            weights=DEFAULT_WEIGHTS.as_dict(),
        ),
        encoding="utf-8",
    )
    click.echo(f"[now-quality] scored {len(articles)} articles" + (" (dry-run, not written)" if dry_run else " and upserted engine.quality_scores"))
    click.echo(f"[now-quality] stubs under {STUB_CHAR_THRESHOLD} chars: {len(stubs)}")
    click.echo(f"[now-quality] report: {report_path}")


@cli.command("series")
@click.option("--url", required=True, help="City db_ref (e.g. now_jakarta) or full DSN.")
@click.option("--apply", is_flag=True, help="Write series_key for NULL rows. Default is dry-run (report only).")
@click.option("--fuzzy-threshold", default=0.87, show_default=True)
@click.option("--report", "report_path", type=click.Path(path_type=Path), default=None,
              help="Markdown report path (default: <db_ref>_series_report.md).")
def series_cmd(url: str, apply: bool, fuzzy_threshold: float, report_path: Path | None) -> None:
    engine = db.make_engine(url)
    articles = db.fetch_articles(engine)
    rows = [
        ArticleRow(id=a.id, title=a.title, published_at=a.published_at, existing_series_key=a.series_key)
        for a in articles
    ]

    result = cluster_titles(rows)
    grouped_norms = {c.normalized for c in result.confident} | {c.normalized for c in result.uncertain}
    result.fuzzy_candidates = find_fuzzy_candidates(rows, grouped_norms, threshold=fuzzy_threshold)

    written = 0
    if apply:
        assignments: list[tuple[int, str]] = []
        for cluster in result.confident:
            for member in cluster.members:
                if member.existing_series_key is None:
                    assignments.append((member.id, cluster.series_key))
        written = db.assign_series_keys_bulk(engine, assignments)

    report_path = report_path or Path(f"{url}_series_report.md")
    report_path.write_text(render_series_report(result, applied=apply), encoding="utf-8")

    click.echo(f"[now-quality] confident series: {len(result.confident)}, uncertain groups: {len(result.uncertain)}, "
               f"fuzzy candidates: {len(result.fuzzy_candidates)}")
    if apply:
        click.echo(f"[now-quality] series_key written for {written} previously-NULL row(s)")
    else:
        click.echo("[now-quality] dry-run -- pass --apply to write series_key (never overwrites an existing value)")
    click.echo(f"[now-quality] report: {report_path}")


if __name__ == "__main__":
    cli()
