"""`now-inspector serve` -- the "runs locally with one command; no build
step" acceptance criterion. Also a `capture` command for grabbing real
rendered HTML to a file (used for the ticket's evidence requirement
without needing a browser)."""

from __future__ import annotations

import click


@click.group()
def cli() -> None:
    """now-inspector -- E3.4 Engine Inspector."""


@cli.command()
@click.option("--url", "db_ref", required=True, help="City db_ref (e.g. now_jakarta, now_bali) or a full DSN.")
@click.option("--host", default="127.0.0.1")
@click.option("--port", default=8899, type=int)
def serve(db_ref: str, host: str, port: int) -> None:
    """Run the Inspector web UI."""
    import uvicorn

    from now_inspector.app import create_app

    app = create_app(db_ref=db_ref)
    uvicorn.run(app, host=host, port=port)


@cli.command()
@click.option("--url", "db_ref", required=True, help="City db_ref (e.g. now_jakarta, now_bali) or a full DSN.")
@click.option("--query", "query", default=None, help="Free-text query to inspect.")
@click.option("--article-id", "article_id", default=None, type=int, help="Article id to inspect.")
@click.option("--out", "out_path", required=True, help="Path to write the rendered HTML to.")
def capture(db_ref: str, query: str | None, article_id: int | None, out_path: str) -> None:
    """Render one report to a static HTML file, without running a server
    -- used to capture real evidence against real data for the ticket
    report (no browser needed)."""
    from fastapi.testclient import TestClient

    from now_inspector.app import create_app

    if not query and article_id is None:
        raise click.UsageError("Pass --query or --article-id.")

    app = create_app(db_ref=db_ref)
    client = TestClient(app)
    params = {}
    if article_id is not None:
        params["article_id"] = str(article_id)
    else:
        params["q"] = query
    resp = client.get("/inspect", params=params)
    resp.raise_for_status()

    with open(out_path, "w", encoding="utf-8") as f:
        f.write(resp.text)
    click.echo(f"[now-inspector] wrote {out_path} ({len(resp.text)} bytes, status {resp.status_code})")


if __name__ == "__main__":
    cli()
