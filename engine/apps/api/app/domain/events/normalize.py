"""Validates the beacon's identifier fields and pulls the two things it
still smuggles through `entity_id` -- a search query and an outbound href --
into their own typed columns.

## History -- decisions C1 and C4 (PROGRESS.md)

`engine.interactions` originally typed `anon_id`, `session_id`, `user_id`,
`entity_id` as `uuid NOT NULL` (0001), but the beacon (E0.4) never emitted
UUIDs for any of them: `anon_id`/`session_id` were 24-char base36 strings,
`user_id` an arbitrary app string, and `entity_id` doubled as a real entity
id, a raw outbound `href`, or search-query text depending on `entity_type`.

E0.5 shipped `stable_uuid`, a deterministic `uuid5` derivation, as a
stopgap so writes didn't fail outright. It preserved join identity (the
same opaque string always derived the same synthetic uuid) but was lossy
for outbound links: hashing an href into a uuid destroys the href, and
partner click attribution / the `ad_events` billing ledger (E4) need the
actual URL, not a hash of it.

Migration 0003 (decision C4) closes this properly instead of continuing to
paper over it:

  * the beacon now emits `crypto.randomUUID()` for `anon_id`/`session_id`
    (a beacon-side change -- not made in this package, see the E0.7 report
    for the exact diff needed), so those two are genuine uuids on arrival;
  * `entity_id` is nullable and, for a row that doesn't reference a real
    entity, is left NULL rather than populated with anything synthetic;
  * the search query (`entity_type == 'search_query'`, decision C1,
    unchanged since 0002) and the outbound href (`entity_type == 'url'`,
    new) are pulled out of the wire's `entity_id` field into `query` and
    `target_url` respectively -- both real, typed, lossless columns.

`stable_uuid` is deleted, not deprecated -- it must never be reached for
either identifiers (which are now validated, not reinterpreted) or for
`entity_id` (which is now nullable, so there is nothing left needing a
synthetic value). Anything that still isn't a genuine UUID where one is
required is a client-payload problem: `InvalidEventIdentifierError`, which
`app/domain/events/service.py` turns into a 4xx, never a 500 and never a
fabricated identifier.

## History -- F66 (PROGRESS.md)

C4 fixed `anon_id`/`session_id`/`user_id`/`entity_id`'s *nullability* and
non-entity encodings, but left `entity_id` itself typed `uuid` for the case
where it *does* name a real entity. That was still wrong: `public.
articles.id` and `public.places.id` (and `public.events.id`) are Payload
integer serials, not uuids, so `interaction_entity_id` below rejected every
real article/place id the beacon could ever send with a 4xx -- the beacon
could record a view of a synthetic uuid entity but never of a real one.
Same bug class as F33 (`engine.quality_scores`/`entity_terms`/
`covisitation`/`rail_cache`, migration 0005) and F44 (`travel_matrix`,
migration 0006), just undiscovered for these two tables until F66.

Migration 0007 widens `interactions.entity_id` (uuid NULL -> text NULL) and
`impressions.entity_id` (uuid NOT NULL -> text NOT NULL) to hold the native
integer PK verbatim -- exactly F33's fix shape, exactly F33's reason for
rejecting a derived-uuid hash instead (hashing an integer PK destroys the
`entity_id::int = articles.id` join). `interaction_entity_id` and
`_impression_params` (service.py) now validate against
`parse_native_entity_id` instead of `parse_uuid` for anything that names a
real entity. `anon_id`/`session_id`/`user_id` are untouched by F66 --
confirmed, not assumed, they genuinely are uuids (beacon emits
`crypto.randomUUID()` since F19) and stay validated by `parse_uuid`.
"""

from __future__ import annotations

import re
import uuid


class InvalidEventIdentifierError(ValueError):
    """A beacon-supplied identifier field failed validation.

    Raised for `anon_id`, `session_id`, or a present `user_id` that isn't a
    genuine UUID, or for an `entity_id` that names a real entity (i.e. not
    one of the two non-entity encodings handled by
    `extract_query`/`extract_target_url` below) but isn't a native integer
    PK (F66/migration 0007 -- this used to require a UUID too, before
    F66). `expected` carries the field-specific description so the message
    stays accurate instead of hardcoding "must be a UUID" for a field that
    no longer needs one. Callers map this to a 4xx -- see
    `app/domain/events/service.py::write_events` and
    `app/api/v1/events.py`.
    """

    def __init__(self, field: str, raw: str, expected: str = "a UUID") -> None:
        self.field = field
        self.raw = raw
        super().__init__(f"{field} must be {expected}, got {raw!r}")


def parse_uuid(raw: str, field: str) -> uuid.UUID:
    """Parses `raw` as a UUID or raises `InvalidEventIdentifierError`.

    No fallback derivation (see module docstring, decision C4). Every
    caller passes a value that is supposed to already be a genuine
    identifier -- `anon_id`, `session_id`, or `user_id`. (`entity_id` used
    to be validated here too, before F66 -- see `parse_native_entity_id`
    below for its current, non-uuid validation.)
    """
    try:
        return uuid.UUID(raw)
    except (ValueError, AttributeError, TypeError):
        raise InvalidEventIdentifierError(field, raw) from None


# `public.articles.id` / `public.places.id` / `public.events.id` are Payload
# integer serials (ARCHITECTURE.md §5) -- every real entity this project has
# today is keyed by one of those three tables' auto-increment integer PK.
# F66's fix stores that PK "verbatim" (F33's phrase, migration 0005's
# docstring) as text, so validation here checks the wire value looks like
# one of those PKs -- a non-negative integer with no leading zero (Payload's
# serial sequence starts at 1 and never produces "007") -- rather than
# accepting an arbitrary string. This is what keeps the "still rejects
# genuine garbage" half of F66's acceptance bar: an empty string, a UUID
# left over from a pre-fix client, an href, or a script-injection attempt
# all fail this pattern and raise `InvalidEventIdentifierError` (-> 4xx),
# exactly as a bad `anon_id` does.
_NATIVE_ENTITY_ID_PATTERN = re.compile(r"^(0|[1-9][0-9]*)$")

# The pattern above bounds SHAPE but not MAGNITUDE, and that gap is real:
# QA.5 posted a 50-digit numeric string, got a 204, and the row persisted --
# then `entity_id::int = articles.id`, the exact join F66 exists to enable,
# raised `value "111...111" is out of range for type integer`. Same failure
# mode as the documented historical-uuid rows, except forward-looking: any
# client could write one today.
#
# Payload's serials are `integer`, not `bigint`, so the real ceiling is
# Postgres's int4 max. Bounding here means a value that would poison the
# join is rejected at write time rather than sitting silently unjoinable --
# which is the whole point of validating this field at all.
_POSTGRES_INT4_MAX = 2_147_483_647


def parse_native_entity_id(raw: str, field: str) -> str:
    """Validates `raw` as a native Payload integer-serial PK and returns it
    unchanged (the value written to `engine.interactions.entity_id` /
    `engine.impressions.entity_id`, both `text` as of migration 0007, is
    the verbatim wire string -- no int() round-trip, so a PK is never
    reformatted, padded, or silently coerced).

    Raises `InvalidEventIdentifierError` (-> 4xx, same family as a bad
    `anon_id`/`session_id`) for anything that is not a bare non-negative
    integer string -- this is deliberately stricter than "is this valid
    `text`", because the whole point of F66 is that this column names a
    real row and a malformed value here would otherwise sit silently
    unjoinable to `public.articles`/`public.places`/`public.events` instead
    of being caught at write time.
    """
    if not _NATIVE_ENTITY_ID_PATTERN.fullmatch(raw):
        raise InvalidEventIdentifierError(field, raw, expected="a native integer id (Payload PK)")
    # Shape is right; check it also fits the column it will be joined against
    # (see _POSTGRES_INT4_MAX above -- found by QA.5).
    if int(raw) > _POSTGRES_INT4_MAX:
        raise InvalidEventIdentifierError(
            field, raw, expected="a native integer id (Payload PK) within int4 range"
        )
    return raw


# Beacon README: "the query text, truncated to 200 chars" -- enforced
# client-side already, re-enforced here defensively in case a future beacon
# build or a hand-rolled client omits the truncation.
_MAX_QUERY_CHARS = 200

# The beacon's one documented search encoding (README "search and the
# missing query field"): kind='search' pairs with this entity_type and the
# literal query text in entity_id. Normalisation triggers on entity_type
# alone (not kind) so a client that gets the pairing slightly wrong still
# lands its query text in the right column rather than being silently lost.
SEARCH_ENTITY_TYPE = "search_query"

# The beacon's encoding for an untagged outbound link -- an anchor with no
# `data-nowb-entity` attribute (engine/packages/beacon/README.md, "Payload
# contract" table + "Programmatic API" notes: "otherwise entity_id falls
# back to the link's href"): `entity_type: "url"`, `entity_id: <raw
# absolute href>`. Mirrors SEARCH_ENTITY_TYPE's trigger-on-entity_type-alone
# design (decision C1) for decision C4's target_url.
OUTBOUND_ENTITY_TYPE = "url"

# Matches schemas.py's _MAX_TEXT_FIELD ceiling already enforced on the wire
# `entity_id` field this is extracted from -- re-asserted here defensively,
# same rationale as _MAX_QUERY_CHARS above.
_MAX_URL_CHARS = 2048


def extract_query(entity_type: str, entity_id: str) -> str | None:
    """Returns the search query text for a `search_query`-typed event, else
    `None`. This is the one place `entity_type == 'search_query'` gets
    special-cased -- see decision C1."""
    if entity_type != SEARCH_ENTITY_TYPE:
        return None
    return entity_id[:_MAX_QUERY_CHARS]


def extract_target_url(entity_type: str, entity_id: str) -> str | None:
    """Returns the outbound href for a `url`-typed event, else `None`.

    This is the fix for decision C4: previously the href landed in
    `entity_id` and was destroyed by `stable_uuid`'s hash. Now it is
    preserved verbatim (truncated defensively) in `engine.interactions.
    target_url`, and `interaction_entity_id` below leaves the row's
    `entity_id` column NULL instead.
    """
    if entity_type != OUTBOUND_ENTITY_TYPE:
        return None
    return entity_id[:_MAX_URL_CHARS]


def interaction_entity_id(entity_type: str, entity_id: str) -> str | None:
    """The value to write into `engine.interactions.entity_id` (text NULL,
    since migration 0007 -- F66) for one interaction row.

    NULL for the two wire encodings that do not name a real entity --
    `search_query` (text goes to `query`) and `url` (href goes to
    `target_url`) -- and a validated native integer PK for everything
    else, which must reference a real article/place/event row in this
    city's `public` schema. Raises `InvalidEventIdentifierError` (-> 4xx)
    rather than fabricating a value if it isn't one.

    Before F66 this called `parse_uuid` and rejected every real
    article/place id with a 4xx, because `public.articles.id`/
    `public.places.id` are Payload integer serials, not uuids -- the
    beacon could record a view of a synthetic uuid entity but never of a
    real one. See the module docstring's "History -- F66" section.
    """
    if entity_type in (SEARCH_ENTITY_TYPE, OUTBOUND_ENTITY_TYPE):
        return None
    return parse_native_entity_id(entity_id, "entity_id")
