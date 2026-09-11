"""FastAPI app factory. Server-rendered Jinja2 HTML, no build step, no
JS framework -- matches the ticket's "internal debug surface, optimise
for information density, not polish" instruction.

One dedicated Connection per request (opened, used, closed) rather than
a pooled Engine handed around, mirroring `now_search.SearchEngine`'s own
documented reasoning: the lexical `pg_temp` cache is session-scoped, so
each request gets a fresh connection and pays the (few-second) warm-up
cost once per request. Fine for an internal debug tool used interactively
by one engineer at a time; NOT the pattern a public endpoint should copy
(see now-search's own warm_up()/reuse-one-connection design for what a
latency-sensitive caller should do instead).
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from now_inspector import service
from now_inspector.connections import city_engine, platform_engine

_TEMPLATES_DIR = Path(__file__).parent / "templates"


def create_app(*, db_ref: str, site_slug: str | None = None) -> FastAPI:
    """`db_ref` has no default -- per ARCHITECTURE.md §3.5, every city is a
    separate DB on the same Postgres instance and this tool must never
    assume which one, so the caller (CLI `--url`) always states it
    explicitly (matches `now-search`'s own `--db` being `required=True`,
    no default).

    `site_slug` is new (F124/F125, T2 decay trust gate) and optional,
    mirroring `now_blender.reranker.BlenderReranker.build`/`now_rails
    .orchestrator.RailsOrchestrator.build`'s own "give both platform_conn
    and site_slug for live config, or omit both for the package default"
    contract: with it, this tool opens a platform-DB connection per
    request and resolves the format facet's term ids plus the site's real
    (possibly tuned) `min_format_confidence`; without it, the trust gate
    still runs but falls back to the package default (0.85) and cannot
    resolve any format's provenance (so it fails closed and discloses
    that via `FreshnessResult.withheld_reason` -- never silently skipped).
    """
    app = FastAPI(title="Engine Inspector")
    templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))
    engine = city_engine(db_ref)
    platform_eng = platform_engine() if site_slug is not None else None

    @app.get("/", response_class=HTMLResponse)
    def index(request: Request):
        return templates.TemplateResponse(request, "index.html", {"query": None, "article_id": None})

    @app.get("/inspect", response_class=HTMLResponse)
    def inspect(
        request: Request,
        q: str | None = Query(default=None),
        article_id: str | None = Query(default=None),
    ):
        aid: int | None = None
        if article_id:
            try:
                aid = int(article_id)
            except ValueError:
                aid = None

        with engine.connect() as conn:
            if platform_eng is not None:
                with platform_eng.connect() as platform_conn:
                    if aid is not None:
                        report = service.build_article_report(conn, aid, platform_conn=platform_conn, site_slug=site_slug)
                    elif q:
                        report = service.build_query_report(conn, q, platform_conn=platform_conn, site_slug=site_slug)
                    else:
                        return templates.TemplateResponse(request, "index.html", {"query": None, "article_id": None})
            elif aid is not None:
                report = service.build_article_report(conn, aid)
            elif q:
                report = service.build_query_report(conn, q)
            else:
                return templates.TemplateResponse(request, "index.html", {"query": None, "article_id": None})

        ctx = {
            "query": report.query,
            "article_id": report.article_id,
            "seed_article": report.seed_article,
            "error": report.error,
            "generator_panels": report.generator_panels,
            "candidates": report.candidates,
            "diversity": report.diversity,
            "filters_status": report.filters_status,
            "title": f"Inspect: {report.query or ('#' + str(report.article_id))}",
        }
        return templates.TemplateResponse(request, "report.html", ctx)

    @app.get("/healthz")
    def healthz():
        return {"status": "ok", "db_ref": db_ref}

    return app
