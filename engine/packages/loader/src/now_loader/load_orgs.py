"""`engine.orgs` <- `partner_roster.jsonl` (E4.1). The one loader module in
this package that writes to the **platform** DB (`now_platform.engine`)
rather than a city DB's `public` schema -- everything else here follows
E1.8's "one-shot JSONL -> city DB" contract, but org candidacy is
platform-wide (ARCHITECTURE.md §5: orgs/partnerships live in
`now_platform`, never per-city), so `--city` does not apply to this
command at all and nothing here imports `now_loader.config`/`dbutil`
(both hard-coded to a city DSN). Connection resolution instead reuses
`now_platform_db.settings.platform_database_url()` -- this package already
depends on `now-platform-db` as a path dependency for exactly this reason:
the `.env`/`NOW_PG_*`/`NOW_PLATFORM_DATABASE_URL` precedence (F52) is
already solved correctly there and has its own test coverage; duplicating
it a third time here would just be a second place for that logic to drift.

**What this loader is not allowed to do**, per the E4.1 ticket: create a
`partnerships` row (every roster entry is a *candidate* org, not a signed
deal), or write a roster guess into an authoritative/confirmed-fact column
(`orgs.type`, `orgs.review_status` past its `'pending'` default). See
`now_platform_db`'s `0004_orgs_roster_provenance` migration docstring for
the full column-by-column reasoning; this module is just what populates
those columns.

Two-pass load, because the roster is flat (`parent_org_slug` is a string
reference to another row in the *same* file, not a real id, and rows are
not topologically sorted -- e.g. the synthesized `intercontinental` parent
appears well after several of its children in file order):

    pass 1: upsert every org by `slug` (ON CONFLICT DO UPDATE), building a
            `slug -> id` map from `RETURNING id`. `parent_org_id` is left
            NULL/untouched in this pass -- the id it needs to point at may
            not exist yet.
    pass 2: for every row with a `parent_org_slug`, UPDATE `parent_org_id`
            from the map built in pass 1. Every `parent_org_slug` in the
            live 1,562-row file resolves to another row in the same file
            (verified: zero dangling references) so this pass never needs
            to fall back to a bare INSERT for a missing parent stub.

Idempotent: `slug` is the upsert key (matches `uq_orgs_slug`), so a rerun
updates the same rows rather than duplicating them, and pass 2 recomputes
the same `parent_org_id` values every time. The one thing a rerun
deliberately does NOT touch is `review_status` (and `type`) on an existing
row -- see the ON CONFLICT column list below -- so a human's review
decision from an earlier load survives a later re-extraction of the same
roster.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.engine import Connection

from now_loader.sources import iter_jsonl

_UPSERT = text(
    """
    INSERT INTO engine.orgs
        (name, slug, website, type_guess, confidence, synthesized, domains,
         link_count, article_count, first_seen, last_seen, rel_audit, notes,
         source, updated_at, created_at)
    VALUES
        (:name, :slug, :website, :type_guess, :confidence, :synthesized, :domains,
         :link_count, :article_count, :first_seen, :last_seen,
         CAST(:rel_audit AS jsonb), :notes, :source, now(), now())
    ON CONFLICT (slug) DO UPDATE
       SET name          = EXCLUDED.name,
           website       = EXCLUDED.website,
           type_guess    = EXCLUDED.type_guess,
           confidence    = EXCLUDED.confidence,
           synthesized   = EXCLUDED.synthesized,
           domains       = EXCLUDED.domains,
           link_count    = EXCLUDED.link_count,
           article_count = EXCLUDED.article_count,
           first_seen    = EXCLUDED.first_seen,
           last_seen     = EXCLUDED.last_seen,
           rel_audit     = EXCLUDED.rel_audit,
           notes         = EXCLUDED.notes,
           source        = EXCLUDED.source,
           updated_at    = now()
       -- Deliberately NOT updated: id, parent_org_id (set in pass 2),
       -- review_status, type, booking_url, logo_media_id -- every one of
       -- those is either human-owned (a reviewer's decision must survive
       -- a re-extraction) or not sourced from this file at all.
    RETURNING id
    """
)

_SET_PARENT = text(
    "UPDATE engine.orgs SET parent_org_id = :parent_org_id, updated_at = now() "
    "WHERE id = :org_id AND parent_org_id IS DISTINCT FROM :parent_org_id"
)


@dataclass
class OrgsLoadResult:
    read: int = 0
    inserted_or_updated: int = 0
    parent_links_set: int = 0
    parent_links_missing: int = 0
    synthesized_count: int = 0
    low_confidence_count: int = 0  # confidence <= 0.6, per this ticket's review threshold
    confidence_histogram: dict[str, int] = field(default_factory=dict)
    slug_to_id: dict[str, str] = field(default_factory=dict)


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    return date.fromisoformat(value)


def load_orgs(conn: Connection, roster_path: Path, *, source_tag: str) -> OrgsLoadResult:
    result = OrgsLoadResult()
    rows = list(iter_jsonl(roster_path))

    # --- pass 1: upsert every org, parent_org_id untouched -------------
    for row in rows:
        result.read += 1

        domains = row.get("domains") or []
        confidence = row.get("confidence")
        synthesized = bool(row.get("synthesized", False))

        if synthesized:
            result.synthesized_count += 1
        if confidence is not None and confidence <= 0.6:
            result.low_confidence_count += 1
        histogram_key = f"{confidence:.2f}" if confidence is not None else "null"
        result.confidence_histogram[histogram_key] = result.confidence_histogram.get(histogram_key, 0) + 1

        org_id = conn.execute(
            _UPSERT,
            {
                "name": row.get("name") or row["org_slug"],
                "slug": row["org_slug"],
                # Directly-observed domain (a real outbound link target in
                # the corpus), not a classifier guess -- safe to treat as a
                # confirmed-fact column. Empty for a synthesized parent
                # (no domain was ever directly linked; see notes).
                "website": f"https://{domains[0]}" if domains else None,
                "type_guess": row.get("type_guess"),
                "confidence": confidence,
                "synthesized": synthesized,
                "domains": domains,
                "link_count": row.get("link_count"),
                "article_count": row.get("article_count"),
                "first_seen": _parse_date(row.get("first_seen")),
                "last_seen": _parse_date(row.get("last_seen")),
                "rel_audit": json.dumps(row.get("rel_audit") or {}),
                "notes": row.get("notes") or [],
                "source": source_tag,
            },
        ).scalar_one()

        result.slug_to_id[row["org_slug"]] = str(org_id)
        result.inserted_or_updated += 1

    # --- pass 2: resolve parent_org_slug -> parent_org_id --------------
    for row in rows:
        parent_slug = row.get("parent_org_slug")
        if not parent_slug:
            continue
        parent_id = result.slug_to_id.get(parent_slug)
        if parent_id is None:
            # Not expected against the shipped roster (every parent_org_slug
            # resolves within the same file -- verified up front), but a
            # future re-extraction could add a child before its parent
            # exists in some partial/filtered run. Fail loud in the report
            # rather than silently leaving parent_org_id NULL forever.
            result.parent_links_missing += 1
            continue
        own_id = result.slug_to_id[row["org_slug"]]
        conn.execute(_SET_PARENT, {"org_id": own_id, "parent_org_id": parent_id})
        result.parent_links_set += 1

    return result
