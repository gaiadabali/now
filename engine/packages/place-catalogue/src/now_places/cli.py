"""`now-places` -- P1.1 triage/rank and P1.2 dedupe/merge.

Every command is a DRY RUN unless given `--apply`. An `--apply` must also
name the database it will write to with `--confirm-db <name>` (the same
value `--db` resolves to), so a stray `--apply` cannot write anywhere by
accident; prove an apply on a scratch copy first:

    now-places triage bali --db now_bali_p1_scratch --apply --confirm-db now_bali_p1_scratch
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

import click

from now_places import db as dbmod
from now_places.dedupe import plan_dedupe
from now_places.merge import MergeRefused, apply_merge, unmerge
from now_places.rank import featured_coverage, queue_order, score_place
from now_places.report import render_dedupe_summary, render_triage, write
from now_places.triage import triage as run_triage

PROJECT_ROOT = Path(__file__).resolve().parents[5]
CITIES = click.Choice(["bali", "jakarta"])


def _extracted_dir(city: str) -> Path:
    return PROJECT_ROOT / city / "content" / "extracted"


def _append_log(path: Path, lines: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as f:
        for line in lines:
            f.write(line + "\n")


def _db_ref(city: str, db: str | None) -> str:
    return db or dbmod.CITY_DB[city]


def _check_apply(apply: bool, confirm_db: str | None, db_ref: str) -> None:
    if apply and confirm_db != db_ref:
        raise click.UsageError(
            f"--apply writes to {db_ref!r}; repeat that name with --confirm-db {db_ref} to proceed."
        )


def _load(city: str, db_ref: str):
    engine = dbmod.make_engine(db_ref)
    places = dbmod.fetch_evidence(engine)
    featured_total = dbmod.total_featured_mentions(engine)
    partnered = dbmod.fetch_partnered(city)
    return engine, places, featured_total, partnered


def _coverage_after_merges(result, plan) -> tuple[int, float]:
    """Top-500 coverage if the proposed auto-merges were applied: each
    survivor absorbs its losers' evidence and the losers leave the queue."""
    absorbed: dict[int, list] = defaultdict(list)
    losers = set()
    for op in plan.merges:
        absorbed[op.survivor.id].append(op.loser)
        losers.add(op.loser.id)
    merged = []
    for p, _ in result.queue:
        if p.id in losers:
            continue
        extra = absorbed.get(p.id, [])
        if extra:
            from dataclasses import replace

            p = replace(
                p,
                featured=p.featured + sum(x.featured for x in extra),
                articles=p.articles + sum(x.articles for x in extra),
                mentions=p.mentions + sum(x.mentions for x in extra),
                newest=max([d for d in [p.newest, *[x.newest for x in extra]] if d is not None], default=None),
            )
        merged.append(p)
    cov = featured_coverage(queue_order(merged), result.coverage.featured_total)
    return cov.featured_in_top, cov.share


@click.group()
def cli() -> None:
    """Place catalogue triage, ranking and dedupe (plan Sec.9, P1.1/P1.2)."""


@cli.command("triage")
@click.argument("city", type=CITIES)
@click.option("--db", default=None, help="Database name or DSN (default: the city's database).")
@click.option("--report", "report_path", type=click.Path(path_type=Path), default=None,
              help="Where to write the markdown report (default: <city>/site/place-triage-report.md).")
@click.option("--with-dedupe/--no-dedupe", default=True, help="Also plan duplicates, for the report's coverage-after-merges line.")
@click.option("--apply", is_flag=True, help="Write status=junk on the proposed rows (pending_review only).")
@click.option("--confirm-db", default=None, help="Required with --apply: the database name being written.")
def triage_cmd(city: str, db: str | None, report_path: Path | None, with_dedupe: bool, apply: bool, confirm_db: str | None) -> None:
    db_ref = _db_ref(city, db)
    _check_apply(apply, confirm_db, db_ref)
    engine, places, featured_total, partnered = _load(city, db_ref)
    result = run_triage(city, places, featured_total, partnered=partnered)
    plan = plan_dedupe(city, places) if with_dedupe else None
    after = _coverage_after_merges(result, plan) if plan else None

    report_path = report_path or (PROJECT_ROOT / city / "site" / "place-triage-report.md")
    write(report_path, render_triage(result, db_ref=db_ref, dedupe=plan, coverage_after_merges=after))

    summary = {
        "city": city,
        "db": db_ref,
        "rows": result.total_rows,
        "proposed_junk": len(result.junk),
        "suspect": len(result.suspect),
        "out_of_region": len(result.out_of_region),
        "queue": len(result.queue),
        "top500_featured_coverage": round(result.coverage.share, 4),
        "top500_featured_coverage_of_real_venues": round(result.coverage.share_of_venues, 4),
        "featured_on_junk_rows": result.coverage.featured_on_junk,
        "top500_featured_coverage_all_rows": round(result.coverage_all_rows.share, 4),
        "top500_featured_coverage_after_merges": round(after[1], 4) if after else None,
        "featured_total": featured_total,
        "partnership_term": result.partnership_term,
        "report": str(report_path),
        "applied": False,
    }
    if apply:
        ids = [p.id for p in result.junk]
        with engine.begin() as conn:
            changed = dbmod.apply_junk(conn, ids)
        log = _extracted_dir(city) / "place_triage_apply_log.jsonl"
        _append_log(log, [json.dumps({"action": "junk", "db": db_ref, "ids": changed})])
        summary.update(applied=True, junk_written=len(changed), apply_log=str(log))
    click.echo(json.dumps(summary, indent=2))


@cli.command("untriage")
@click.argument("city", type=CITIES)
@click.option("--db", default=None)
@click.option("--log", "log_path", type=click.Path(exists=True, path_type=Path), required=True,
              help="A place_triage_apply_log.jsonl written by `triage --apply`.")
@click.option("--apply", is_flag=True)
@click.option("--confirm-db", default=None)
def untriage_cmd(city: str, db: str | None, log_path: Path, apply: bool, confirm_db: str | None) -> None:
    """Reverse `triage --apply`: junk rows from the log go back to pending_review."""
    db_ref = _db_ref(city, db)
    _check_apply(apply, confirm_db, db_ref)
    ids: list[int] = []
    for line in log_path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rec = json.loads(line)
            if rec.get("db") == db_ref and rec.get("action") == "junk":
                ids.extend(rec["ids"])
    if not apply:
        click.echo(json.dumps({"city": city, "db": db_ref, "would_revert": len(ids), "applied": False}))
        return
    with dbmod.make_engine(db_ref).begin() as conn:
        changed = dbmod.revert_junk(conn, ids)
    click.echo(json.dumps({"city": city, "db": db_ref, "reverted": len(changed), "applied": True}))


@cli.command("rank")
@click.argument("city", type=CITIES)
@click.option("--db", default=None)
@click.option("--top", "top_n", type=int, default=500, show_default=True)
@click.option("--csv", "csv_path", type=click.Path(path_type=Path), default=None, help="Also write the top list as CSV.")
@click.option("--apply", is_flag=True, help="Materialise the score into places.quality_score.")
@click.option("--confirm-db", default=None)
def rank_cmd(city: str, db: str | None, top_n: int, csv_path: Path | None, apply: bool, confirm_db: str | None) -> None:
    db_ref = _db_ref(city, db)
    _check_apply(apply, confirm_db, db_ref)
    engine, places, featured_total, partnered = _load(city, db_ref)
    result = run_triage(city, places, featured_total, partnered=partnered, top_n=top_n)
    if csv_path:
        import csv

        csv_path.parent.mkdir(parents=True, exist_ok=True)
        with csv_path.open("w", encoding="utf-8", newline="") as f:
            w = csv.writer(f)
            w.writerow(["rank", "id", "name", "score", "featured", "articles", "suspect", "other_region"])
            for i, (p, s) in enumerate(result.queue[:top_n], start=1):
                w.writerow([i, p.id, p.name, f"{s:.3f}", p.featured, p.articles,
                            p.flags.get("reason") if p.flags.get("tier") == "suspect" else "",
                            p.flags.get("region_match") if p.flags.get("out_of_region") else ""])
    out = {
        "city": city,
        "db": db_ref,
        "queue": len(result.queue),
        "top_n": top_n,
        "featured_total": featured_total,
        "featured_in_top": result.coverage.featured_in_top,
        "coverage": round(result.coverage.share, 4),
        "coverage_of_real_venues": round(result.coverage.share_of_venues, 4),
        "coverage_all_rows": round(result.coverage_all_rows.share, 4),
        "partnership_term": result.partnership_term,
        "head": [{"id": p.id, "name": p.name, "score": round(s, 3)} for p, s in result.queue[:10]],
        "applied": False,
    }
    if apply:
        scores = {p.id: score_place(p) for p, _ in result.queue}
        with engine.begin() as conn:
            out["quality_scores_written"] = dbmod.write_quality_scores(conn, scores)
        out["applied"] = True
    click.echo(json.dumps(out, indent=2, ensure_ascii=False))


@cli.command("dedupe")
@click.argument("city", type=CITIES)
@click.option("--db", default=None)
@click.option("--queue", "queue_path", type=click.Path(path_type=Path), default=None,
              help="Where to write the review queue (default: <city>/content/extracted/place_dedupe_review_queue.jsonl).")
@click.option("--report", "report_path", type=click.Path(path_type=Path), default=None)
@click.option("--apply", is_flag=True, help="Apply the >= 0.85 merges, one transaction each. Queued pairs are never merged.")
@click.option("--confirm-db", default=None)
@click.option("--by", "actor", default="now-places dedupe", show_default=True, help="Recorded as the merge's actor.")
def dedupe_cmd(city: str, db: str | None, queue_path: Path | None, report_path: Path | None, apply: bool, confirm_db: str | None, actor: str) -> None:
    db_ref = _db_ref(city, db)
    _check_apply(apply, confirm_db, db_ref)
    engine = dbmod.make_engine(db_ref)
    places = dbmod.fetch_evidence(engine)
    plan = plan_dedupe(city, places)

    queue_path = queue_path or (_extracted_dir(city) / "place_dedupe_review_queue.jsonl")
    queue_path.parent.mkdir(parents=True, exist_ok=True)
    with queue_path.open("w", encoding="utf-8", newline="\n") as f:
        for q in plan.queued:
            f.write(json.dumps({"a": {"id": q.a.id, "name": q.a.name}, "b": {"id": q.b.id, "name": q.b.name},
                                "score": round(q.score, 4), "why": q.why}, ensure_ascii=False) + "\n")
    report_path = report_path or (PROJECT_ROOT / city / "site" / "place-dedupe-report.md")
    write(report_path, f"# Place duplicates — {city}\n\nAgainst `{db_ref}`.\n\n" + render_dedupe_summary(plan) + "\n")

    out = {"city": city, "db": db_ref, "candidates": plan.candidates, "pairs_scored": plan.pairs_scored,
           "merges_proposed": len(plan.merges), "queued": len(plan.queued), "queue": str(queue_path),
           "report": str(report_path), "applied": False}
    if apply:
        done, refused, log_lines = 0, [], []
        for op in plan.merges:
            try:
                with engine.begin() as conn:
                    rec = apply_merge(conn, op.loser.id, op.survivor.id, score=op.score, by=actor)
                log_lines.append(json.dumps({"db": db_ref, **json.loads(rec.as_json())}, ensure_ascii=False))
                done += 1
            except MergeRefused as e:
                refused.append({"loser": op.loser.id, "survivor": op.survivor.id, "why": str(e)})
        log = _extracted_dir(city) / "place_merge_log.jsonl"
        _append_log(log, log_lines)
        out.update(applied=True, merged=done, refused=refused, merge_log=str(log))
    click.echo(json.dumps(out, indent=2, ensure_ascii=False))


@cli.command("merge")
@click.argument("city", type=CITIES)
@click.argument("loser", type=int)
@click.argument("survivor", type=int)
@click.option("--db", default=None)
@click.option("--apply", is_flag=True)
@click.option("--confirm-db", default=None)
@click.option("--by", "actor", default="now-places merge", show_default=True)
def merge_cmd(city: str, loser: int, survivor: int, db: str | None, apply: bool, confirm_db: str | None, actor: str) -> None:
    """Merge one place into another (an editor's decision on a queued pair).
    Without --apply the merge runs inside a transaction that is rolled back,
    so the dry run reports exactly what would move."""
    db_ref = _db_ref(city, db)
    _check_apply(apply, confirm_db, db_ref)
    engine = dbmod.make_engine(db_ref)
    conn = engine.connect()
    trans = conn.begin()
    try:
        rec = apply_merge(conn, loser, survivor, score=None, by=actor)
    except MergeRefused as e:
        trans.rollback()
        raise click.ClickException(str(e)) from e
    if apply:
        trans.commit()
        _append_log(_extracted_dir(city) / "place_merge_log.jsonl", [json.dumps({"db": db_ref, **json.loads(rec.as_json())}, ensure_ascii=False)])
    else:
        trans.rollback()
    conn.close()
    click.echo(json.dumps({"applied": apply, **json.loads(rec.as_json())}, indent=2, ensure_ascii=False))


@cli.command("unmerge")
@click.argument("city", type=CITIES)
@click.argument("loser", type=int)
@click.option("--db", default=None)
@click.option("--apply", is_flag=True)
@click.option("--confirm-db", default=None)
@click.option("--by", "actor", default="now-places unmerge", show_default=True)
def unmerge_cmd(city: str, loser: int, db: str | None, apply: bool, confirm_db: str | None, actor: str) -> None:
    """Reverse a merge exactly, from the audit entry on the survivor."""
    db_ref = _db_ref(city, db)
    _check_apply(apply, confirm_db, db_ref)
    engine = dbmod.make_engine(db_ref)
    conn = engine.connect()
    trans = conn.begin()
    try:
        rec = unmerge(conn, loser, by=actor)
    except MergeRefused as e:
        trans.rollback()
        raise click.ClickException(str(e)) from e
    if apply:
        trans.commit()
        _append_log(_extracted_dir(city) / "place_merge_log.jsonl", [json.dumps({"db": db_ref, **json.loads(rec.as_json())}, ensure_ascii=False)])
    else:
        trans.rollback()
    conn.close()
    click.echo(json.dumps({"applied": apply, **json.loads(rec.as_json())}, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    cli()
