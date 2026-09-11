from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .client import RestClient
from .config import Config
from .harvest import content as content_mod
from .harvest import media as media_mod
from .sink import ResumableSink, read_jsonl

Projector = Callable[[dict[str, Any]], dict[str, Any]]


@dataclass(frozen=True)
class Collection:
    key: str
    endpoint: str
    filename: str
    projector: Projector | None = None
    # Needs the term-name index built from categories+tags first.
    needs_terms: bool = False
    extra: dict[str, Any] = field(default_factory=dict)


# The harvest order matters: taxonomy and users come before posts so post rows
# can carry term *names* the way extracted/articles.jsonl does.
COLLECTIONS: tuple[Collection, ...] = (
    Collection("categories", "categories", "categories.jsonl", content_mod.project_term),
    Collection("tags", "tags", "tags.jsonl", content_mod.project_term),
    Collection("users", "users", "users.jsonl", content_mod.project_user),
    Collection("posts", "posts", "articles.jsonl", needs_terms=True),
    Collection("pages", "pages", "pages.jsonl", needs_terms=True),
    Collection("events", "upcoming-events", "events.jsonl", needs_terms=True),
    Collection("media", "media", "attachments.jsonl", media_mod.project),
    Collection("comments", "comments", "comments.jsonl", content_mod.project_comment),
)

COLLECTIONS_BY_KEY = {c.key: c for c in COLLECTIONS}


@dataclass
class CollectionResult:
    key: str
    endpoint: str
    path: Path
    reported_total: int | None
    written: int
    unique_ids: int
    pages: int
    resumed_from: int
    seconds: float
    context: str

    @property
    def complete(self) -> bool:
        """Written at least as many unique rows as the API said existed.

        ``>=`` not ``==``: a long harvest can legitimately pick up a post
        published while it was running, and ordering by ascending id means
        that lands at the end rather than corrupting earlier pages.
        """
        return self.reported_total is None or self.unique_ids >= self.reported_total

    def as_dict(self) -> dict[str, Any]:
        return {
            "collection": self.key,
            "endpoint": self.endpoint,
            "file": self.path.name,
            "reported_total": self.reported_total,
            "written": self.written,
            "unique_ids": self.unique_ids,
            "pages": self.pages,
            "resumed_from_page": self.resumed_from,
            "seconds": round(self.seconds, 1),
            "context": self.context,
            "complete": self.complete,
        }


def harvest_collection(
    client: RestClient,
    config: Config,
    collection: Collection,
    *,
    resume: bool = False,
    context: str = "view",
    term_index: dict[int, str] | None = None,
    tag_index: dict[int, str] | None = None,
    progress: Callable[[str], None] | None = None,
) -> CollectionResult:
    out_path = config.ensure_output_dir() / collection.filename
    started = time.monotonic()

    extra = dict(collection.extra)
    if context != "view":
        extra["context"] = context

    def emit(message: str) -> None:
        if progress:
            progress(message)

    with ResumableSink(out_path, collection.endpoint, resume=resume) as sink:
        resumed_from = sink.last_completed_page
        if resumed_from:
            emit(f"  {collection.key}: resuming after page {resumed_from}")

        pages = 0
        reported_total: int | None = None
        for page, records, total in client.paginate(
            collection.endpoint, start_page=sink.start_page, extra=extra
        ):
            if total is not None:
                reported_total = total
            if collection.needs_terms:
                projected = [
                    content_mod.project_post(r, term_index, tag_index) for r in records
                ]
            elif collection.projector is not None:
                projected = [collection.projector(r) for r in records]
            else:
                projected = list(records)
            sink.write_page(page, projected)
            pages += 1
            if pages == 1 or pages % 10 == 0:
                emit(
                    f"  {collection.key}: page {page} "
                    f"({sink.records_written}/{reported_total or '?'})"
                )

        written = sink.records_written
        if resumed_from and reported_total is None:
            # Every page was already on disk, so no response carried the
            # header. Ask for it explicitly rather than reporting "unknown".
            reported_total = client.total(collection.endpoint)

    rows = read_jsonl(out_path)
    unique = len({r.get("wp_id") or r.get("term_id") or r.get("id") for r in rows})

    result = CollectionResult(
        key=collection.key,
        endpoint=collection.endpoint,
        path=out_path,
        reported_total=reported_total,
        written=written,
        unique_ids=unique,
        pages=pages,
        resumed_from=resumed_from,
        seconds=time.monotonic() - started,
        context=context,
    )
    if result.complete:
        ResumableSink(out_path, collection.endpoint, resume=True).discard_state()
    return result


def harvest_site(
    config: Config,
    keys: list[str] | None = None,
    *,
    resume: bool = False,
    context: str = "view",
    client: RestClient | None = None,
    progress: Callable[[str], None] | None = None,
) -> list[CollectionResult]:
    selected = [COLLECTIONS_BY_KEY[k] for k in (keys or list(COLLECTIONS_BY_KEY))]
    selected.sort(key=lambda c: COLLECTIONS.index(c))

    owns = client is None
    client = client or RestClient(config)
    results: list[CollectionResult] = []
    try:
        term_index: dict[int, str] = {}
        tag_index: dict[int, str] = {}

        # Any post-bearing collection needs term names. If the caller did not
        # select the taxonomies, read them off disk from an earlier run rather
        # than silently emitting empty category lists.
        if any(c.needs_terms for c in selected):
            for key, target in (("categories", term_index), ("tags", tag_index)):
                if key in {c.key for c in selected}:
                    continue
                path = config.output_dir / COLLECTIONS_BY_KEY[key].filename
                if path.exists():
                    target.update(content_mod.name_index(read_jsonl(path)))

        for collection in selected:
            result = harvest_collection(
                client,
                config,
                collection,
                resume=resume,
                context=context,
                term_index=term_index,
                tag_index=tag_index,
                progress=progress,
            )
            results.append(result)
            if collection.key == "categories":
                term_index.update(content_mod.name_index(read_jsonl(result.path)))
            elif collection.key == "tags":
                tag_index.update(content_mod.name_index(read_jsonl(result.path)))
    finally:
        if owns:
            client.close()
    return results
