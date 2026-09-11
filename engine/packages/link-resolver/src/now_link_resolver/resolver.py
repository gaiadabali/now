"""The two-lookup resolution Sec.11 describes:

    mention(place_id) -> place.org_id -> active partnership (place, else org)

Lookup 1 (city DB): fetch the place's `org_id`/`slug`/`name`. `place_id`
has no FK into the platform DB (F22 -- places live per-city, a different
database; cross-database joins are impossible in Postgres), so this is
always a separate round trip, never a join.

Lookup 2 (platform DB, up to two queries): place-level partnership first;
only if that finds nothing, fall back to org-level using the org_id from
lookup 1. Both queries read `engine.partnerships_active` -- the
query-time view E4.1 shipped -- so liveness (`status`/`starts_at`/
`ends_at` vs `now()`) is never re-derived here, exactly as that
package's contract requires. A row simply is or is not in the view on
this SELECT; there is nothing to expire, cache-invalidate, or re-run.

F62 left the tie-break for "more than one active partnership on the same
(site, org) or (site, place)" to this package on purpose (deliberately no
DB uniqueness constraint, to allow a queued renewal to coexist with the
current contract). The tie-break here is `ORDER BY starts_at DESC NULLS
LAST, id DESC LIMIT 1` -- prefer the most recently started row, and
`id DESC` only to make the choice deterministic on an exact tie (starts_at
NULL vs NULL, or identical timestamps); this has no product meaning
beyond determinism.

Known cross-package gap (see package README / ticket report): `places.id`
in the shipped Payload schema is a Postgres `serial integer`
(`now_jakarta.public.places.id`), but `engine.partnerships.place_id` is
`uuid` (E4.1, following the architecture sketch's assumption that place
ids would be uuids). A real integer place id can never be stored in that
column, so today no *real* Payload place can have a place-level
partnership -- only org-level partnerships are reachable for real places
until that mismatch is resolved (belongs to E4.1/a future migration; out
of this package's scope, which owns no schema and writes no migration).
Every SQL comparison in this module casts the *column* to `::text` rather
than casting the input to the column's type, specifically so a
non-uuid-shaped place_id (e.g. `"42"`) fails closed (no match) instead of
raising `invalid input syntax for type uuid` -- see `_place_level_lookup`.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.engine import Connection

from now_link_resolver.types import LinkDecision, Tier


@dataclass(frozen=True)
class PlaceRecord:
    place_id: str
    org_id: str | None
    slug: str
    name: str


PLACES_TABLE = "public.places"


def fetch_place(city_conn: Connection, place_id: str, *, places_table: str = PLACES_TABLE) -> PlaceRecord | None:
    """Lookup 1 -- city DB. `id::text` on the column (not `place_id::uuid`
    on the input) so this works whether the city DB's `places.id` is the
    shipped `serial integer` or a future uuid, without raising on either.

    `places_table` defaults to the real `public.places` and is only ever
    overridden by tests, pointed at a session-scoped synthetic TEMP TABLE
    (`now_filters`'s existing convention -- see that package's
    `synthetic.py`) since `place_mentions` -- and therefore any real
    mention to resolve -- is empty archive-wide (E2.3 blocked). Production
    code never passes this argument.
    """
    row = city_conn.execute(
        text(
            f"""
            SELECT id::text AS place_id, org_id, slug, name
            FROM {places_table}
            WHERE id::text = :place_id
            """
        ),
        {"place_id": place_id},
    ).mappings().first()
    if row is None:
        return None
    return PlaceRecord(place_id=row["place_id"], org_id=row["org_id"], slug=row["slug"], name=row["name"])


_PARTNERSHIP_COLUMNS = """
    id::text AS partnership_id, org_id::text AS org_id, place_id::text AS place_id,
    tier, custom_url, utm_template, show_badge, badge_label
"""

_ORDER_TIE_BREAK = "ORDER BY starts_at DESC NULLS LAST, id DESC LIMIT 1"


def _place_level_lookup(platform_conn: Connection, site_id: str, place_id: str) -> dict | None:
    row = platform_conn.execute(
        text(
            f"""
            SELECT {_PARTNERSHIP_COLUMNS}
            FROM engine.partnerships_active
            WHERE site_id = :site_id AND place_id::text = :place_id
            {_ORDER_TIE_BREAK}
            """
        ),
        {"site_id": site_id, "place_id": place_id},
    ).mappings().first()
    return dict(row) if row is not None else None


def _org_level_lookup(platform_conn: Connection, site_id: str, org_id: str) -> dict | None:
    row = platform_conn.execute(
        text(
            f"""
            SELECT {_PARTNERSHIP_COLUMNS}
            FROM engine.partnerships_active
            WHERE site_id = :site_id AND org_id::text = :org_id
            {_ORDER_TIE_BREAK}
            """
        ),
        {"site_id": site_id, "org_id": org_id},
    ).mappings().first()
    return dict(row) if row is not None else None


def resolve_mention(
    city_conn: Connection,
    platform_conn: Connection,
    *,
    site_id: str,
    place_id: str,
    places_table: str = PLACES_TABLE,
) -> LinkDecision:
    """Resolve one `place_id` mention to a `LinkDecision`, right now, from
    whatever is currently effective. Read-only: issues no writes, and
    calling it twice with unchanged data always returns an identical
    decision (idempotent, side-effect-free -- see tests/test_reversion.py
    and tests/test_render.py for both properties exercised directly).
    """
    place = fetch_place(city_conn, place_id, places_table=places_table)
    if place is None:
        # Unknown place (e.g. a stale mention after deletion): nothing to
        # link to, nothing to attribute. Render as plain text.
        return LinkDecision(tier="free", place_id=place_id, resolved_via="none")

    partnership = _place_level_lookup(platform_conn, site_id, place_id)
    resolved_via = "place"
    if partnership is None and place.org_id:
        partnership = _org_level_lookup(platform_conn, site_id, place.org_id)
        resolved_via = "org"
    if partnership is None:
        resolved_via = "none"

    if partnership is None:
        return LinkDecision(tier="free", place_id=place_id, slug=place.slug, resolved_via="none")

    tier: Tier = partnership["tier"]  # type: ignore[assignment]
    if tier == "paid":
        external_url = partnership["custom_url"] or f"https://{place.name}"  # placeholder if unset
        return LinkDecision(
            tier="paid",
            place_id=place_id,
            slug=place.slug,
            partnership_id=partnership["partnership_id"],
            org_id=partnership["org_id"],
            external_url=external_url,
            show_badge=bool(partnership["show_badge"]),
            badge_label=partnership["badge_label"] or "Partner",
            utm_template=partnership["utm_template"],
            resolved_via=resolved_via,
        )
    if tier == "listed":
        return LinkDecision(
            tier="listed",
            place_id=place_id,
            slug=place.slug,
            partnership_id=partnership["partnership_id"],
            org_id=partnership["org_id"],
            resolved_via=resolved_via,
        )
    # tier == "free": an explicit free-tier partnership row still renders
    # as plain text -- tier controls link rendering only (Sec.11: "Tier
    # controls link rendering only"), but we keep the attribution.
    return LinkDecision(
        tier="free",
        place_id=place_id,
        slug=place.slug,
        partnership_id=partnership["partnership_id"],
        org_id=partnership["org_id"],
        resolved_via=resolved_via,
    )


def resolve_mentions(
    city_conn: Connection,
    platform_conn: Connection,
    *,
    site_id: str,
    place_ids: list[str],
    places_table: str = PLACES_TABLE,
) -> dict[str, LinkDecision]:
    """Bulk convenience wrapper -- one `LinkDecision` per distinct place_id.
    No batching optimisation attempted (out of this ticket's scope); each
    lookup is independent and safe to parallelise later without changing
    behaviour, since none of it is stateful."""
    return {
        pid: resolve_mention(city_conn, platform_conn, site_id=site_id, place_id=pid, places_table=places_table)
        for pid in dict.fromkeys(place_ids)  # de-dup, preserve order
    }
