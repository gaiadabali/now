"""The proof that a reviewer's decision reaches `engine.entity_terms`.

    uv run python scripts/verify_classification_reviewed.py \
        --site <slug> --entity-id <id> --facet type --to <term-slug>

Runs the real consumer (`app.consumer.DomainEventWorker`) against the real
Redis Stream and the real city database, on a real row, and prints the
`engine.entity_terms` state before and after. Companion to
`engine/packages/cms/scripts/verify-review-no-clobber.mjs`, which proves the
other half (a classifier re-run cannot clobber the row this writes) and which
had to *simulate* this consumer with raw SQL because it did not exist.

Four things it demonstrates, in order:

  1. **The decision lands.** `source` moves `ai` -> `editor`, confidence to a
     human 1.0, and the superseded term's row is gone rather than sitting
     beside the new one.
  2. **Redelivery is safe.** The identical message is appended a second time
     and consumed again; the resulting rows are compared byte for byte with
     the first result.
  3. **Supersession is facet-wide, not `previous_term_id`-wide.** A second
     stale row is seeded in the same facet — one the event does NOT name —
     standing in for an article corrected twice, where the second event still
     reports the AI's original guess as `previous_term_id`. A
     `previous_term_id` delete leaves it behind; this does not.
  4. **It puts the row back.** The fixture is a real article in a real city
     database and the decision here is invented, not a reviewer's. Everything
     is restored at the end, and the restore is printed too. `--keep` opts
     out.

**A proof-only consumer group.** `--group` defaults to a throwaway name
created at `$` (new messages only). The production group,
`now-embeddings-worker`, carries a backlog of real `article.published`
messages; joining it here would drag the whole re-embed backlog through an
offline embedding provider as a side effect of a verification run. The
delivery path being proved — XREADGROUP, the handler, XACK — is identical
either way, because a Redis consumer group is just a cursor.

Connection settings come from the same `NOW_PG_*` / `REDIS_URL` environment
every other tool here reads; nothing is hardcoded and no city is named.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import uuid
from datetime import datetime, timezone

import redis
from now_db.sites_registry import get_site
from now_embeddings.connections import city_engine, platform_engine
from sqlalchemy import text

from app import classification
from app.consumer import DomainEventWorker

STREAM = "now:domain-events:stream"

ROWS_SQL = text(
    """
    select term_id::text, source, confidence, weight
    from engine.entity_terms
    where entity_type = :entity_type and entity_id = :entity_id
      and term_id = any(cast(:facet_term_ids as uuid[]))
    order by term_id
    """
)


def rows_for(city, entity_type: str, entity_id: str, term_ids: list[str]) -> list[tuple]:
    with city.connect() as conn:
        return [
            tuple(r)
            for r in conn.execute(
                ROWS_SQL,
                {
                    "entity_type": entity_type,
                    "entity_id": entity_id,
                    "facet_term_ids": term_ids,
                },
            )
        ]


def show(label: str, rows: list[tuple], slugs: dict[str, str]) -> None:
    print(f"\n  {label}")
    if not rows:
        print("    (no rows)")
    for term_id, source, confidence, weight in rows:
        print(
            f"    term={slugs.get(term_id, term_id)}  source={source}  "
            f"confidence={confidence}  weight={weight}"
        )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--site", required=True, help="slug in now_platform.engine.sites")
    ap.add_argument("--entity-id", required=True)
    ap.add_argument("--entity-type", default="article")
    ap.add_argument("--facet", default="type")
    ap.add_argument("--to", required=True, help="term slug the reviewer chose")
    ap.add_argument("--group", default=f"verify-classification-{uuid.uuid4().hex[:8]}")
    ap.add_argument("--keep", action="store_true", help="do not restore the original rows")
    args = ap.parse_args()

    platform = platform_engine()
    with platform.connect() as conn:
        site = get_site(conn, args.site)
        if site is None:
            print(f"no site {args.site!r} in engine.sites", file=sys.stderr)
            return 1
        term_rows = conn.execute(
            text(
                "select t.slug, t.id::text from engine.terms t "
                "join engine.facets f on f.id = t.facet_id where f.key = :facet"
            ),
            {"facet": args.facet},
        ).all()
    by_slug = {r[0]: r[1] for r in term_rows}
    slugs = {r[1]: r[0] for r in term_rows}
    shape = classification.load_facet_shape(platform, args.facet)
    if shape is None:
        print(f"no facet {args.facet!r} in the platform vocabulary", file=sys.stderr)
        return 1
    new_term_id = by_slug.get(args.to)
    if new_term_id is None:
        print(f"no term {args.to!r} in facet {args.facet!r}", file=sys.stderr)
        return 1

    city = city_engine(site.db_ref)
    entity_id = str(args.entity_id)
    key = {"entity_type": args.entity_type, "entity_id": entity_id}

    print(f"site={site.slug} db={site.db_ref} facet={args.facet} "
          f"cardinality={shape.cardinality} {args.entity_type}:{entity_id}")

    before = rows_for(city, args.entity_type, entity_id, shape.term_ids)
    show("BEFORE", before, slugs)
    if not before:
        print("\n  nothing to supersede — pick an entity that already carries a row "
              "for this facet, or the proof shows nothing.", file=sys.stderr)
        return 1

    # `previous_term_id` is what the CMS puts on the event: the AI's ORIGINAL
    # proposal from the review row, which for a first correction is whatever
    # is in the table now.
    previous_term_id = before[0][0]

    event = {
        "event": classification.EVENT,
        "site_slug": site.slug,
        "entity_type": args.entity_type,
        "entity_id": int(entity_id) if entity_id.isdigit() else entity_id,
        "occurred_at": datetime.now(timezone.utc).isoformat(),
        "payload": {
            "review_id": f"verify-{uuid.uuid4().hex[:8]}",
            "facet_key": args.facet,
            "term_id": new_term_id,
            "previous_term_id": previous_term_id,
            "value": args.to,
            "review_state": "corrected",
            "source": "editor",
            "confidence": 1,
            "reviewed_by": None,
            "reviewed_at": datetime.now(timezone.utc).isoformat(),
        },
    }
    message = json.dumps(event)

    r = redis.Redis.from_url(
        os.environ.get("REDIS_URL", "redis://localhost:16379/0"), decode_responses=True
    )
    # `$` — only messages appended after this point. See the module docstring
    # for why this run must not join the production group.
    try:
        r.xgroup_create(STREAM, args.group, id="$", mkstream=True)
    except redis.ResponseError as exc:
        if "BUSYGROUP" not in str(exc):
            raise

    import now_embeddings.worker as embed_worker

    embed_worker.GROUP = args.group
    from now_embeddings.cli import _provider

    # `offline`, not `local`: no event in this run reaches the re-embed
    # handler, and constructing the ONNX provider would download model weights
    # to prove something about classification.
    worker = DomainEventWorker(
        provider=_provider("offline"), redis_url=os.environ.get("REDIS_URL")
    )

    def publish_and_consume(label: str) -> None:
        message_id = r.xadd(STREAM, {"event": message})
        result = worker.run_once(block_ms=2000)
        print(f"\n  [{label}] xadd {message_id} -> processed={result.processed} "
              f"errors={result.errors} pending={r.xpending(STREAM, args.group)['pending']}")

    publish_and_consume("deliver")
    after = rows_for(city, args.entity_type, entity_id, shape.term_ids)
    show("AFTER", after, slugs)

    publish_and_consume("redeliver the identical message")
    after_replay = rows_for(city, args.entity_type, entity_id, shape.term_ids)
    show("AFTER REDELIVERY", after_replay, slugs)
    print(f"\n  idempotent: {after == after_replay}")

    # Scenario 3: a stale row the event does not name. This is what an article
    # corrected twice looks like — the second event still reports the AI's
    # first guess as previous_term_id, so a previous_term_id-scoped delete
    # would leave this behind and the article would carry two types.
    unnamed = next((t for t in shape.term_ids if t not in {new_term_id, previous_term_id}), None)
    if unnamed and shape.single_valued:
        with city.begin() as conn:
            conn.execute(
                text(
                    "insert into engine.entity_terms "
                    "(entity_type, entity_id, term_id, weight, source, confidence) "
                    "values (:entity_type, :entity_id, cast(:term_id as uuid), 1.0, 'ai', 0.42) "
                    "on conflict do nothing"
                ),
                {**key, "term_id": unnamed},
            )
        show("SEEDED a stale row the event does not name", rows_for(city, args.entity_type, entity_id, shape.term_ids), slugs)
        publish_and_consume("deliver again, with the unnamed stale row present")
        show("AFTER", rows_for(city, args.entity_type, entity_id, shape.term_ids), slugs)

    if args.keep:
        print("\n  --keep: rows left as the decision left them")
    else:
        with city.begin() as conn:
            conn.execute(
                text(
                    "delete from engine.entity_terms where entity_type = :entity_type "
                    "and entity_id = :entity_id and term_id = any(cast(:ids as uuid[]))"
                ),
                {**key, "ids": shape.term_ids},
            )
            for term_id, source, confidence, weight in before:
                conn.execute(
                    text(
                        "insert into engine.entity_terms "
                        "(entity_type, entity_id, term_id, weight, source, confidence) "
                        "values (:entity_type, :entity_id, cast(:term_id as uuid), "
                        ":weight, :source, :confidence)"
                    ),
                    {**key, "term_id": term_id, "weight": weight,
                     "source": source, "confidence": confidence},
                )
        restored = rows_for(city, args.entity_type, entity_id, shape.term_ids)
        show("RESTORED (the decision here was invented, not a reviewer's)", restored, slugs)
        assert restored == before, "restore did not reproduce the original rows"

    r.xgroup_destroy(STREAM, args.group)
    print(f"\n  proof consumer group {args.group} destroyed; "
          "the production group was never touched")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
