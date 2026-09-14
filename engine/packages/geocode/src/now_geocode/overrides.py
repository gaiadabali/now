"""Rung 0 — human-verified corrections, ahead of every automated source.

Loads `jakarta/site/place-overrides.jsonl`: coordinates a person looked
up and cited, for rows no geocoder gets right. It sits above rung 1
(existing coordinates) because a human who checked the venue's own
listing outranks a free-seed point of unknown vintage — the whole reason
the file exists is that some seed and geocode answers are wrong.

**Override data is source, not derived.** It lives under `jakarta/site/`
and is tracked in git, unlike `jakarta/content/extracted/`, because
nothing can regenerate a human verification. See
`jakarta/site/place-overrides.md` for the research trail behind the
current entries.

## Three actions

| action | meaning | resulting row |
|---|---|---|
| `override` | use these coordinates | `RESOLVED`, rung `manual_override` |
| `drop` | this has no trustworthy coordinate | `UNRESOLVED`, coordinate stripped |
| `merge_into` | duplicate of another candidate | `REJECTED`, flagged, points at the survivor |

`drop` does **not** delete the row. It removes a *wrong* coordinate,
leaving the place in the deliverable, unresolved, with the reason
attached — the same "never silently drop" contract as `quality.py`. It
exists for rows like `Salon Bali`, where the honest answer is "nobody
knows", and `The Great 50 Show - Bali`, which turned out to be a 2019
circus run rather than a venue.

`merge_into` likewise keeps the row rather than vanishing it: a
duplicate is emitted `REJECTED` with `merged_duplicate` and a pointer to
the surviving `place_key`, so the merge is auditable and the output row
count stays stable for downstream consumers.

## Every override must cite a source

`load_overrides` rejects an `override` entry with an empty `sources`
list. An uncited coordinate is indistinguishable from a fabricated one,
and this package's one hard rule is that it never invents a coordinate.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

VALID_ACTIONS = ("override", "drop", "merge_into")

# Rows whose keys start with "_" are documentation (the file's own header
# carries `_comment` and `_schema`), not entries.
_DOC_PREFIX = "_"


class OverrideError(ValueError):
    """A malformed overrides file. Raised eagerly at load time — a typo
    in a hand-edited corrections file must fail the run, not silently
    skip a correction someone believed was applied."""


@dataclass(frozen=True)
class Override:
    place_key: str
    name: str
    action: str
    lat: float | None
    lng: float | None
    confidence: float
    sources: tuple[str, ...]
    note: str
    verified_on: str | None = None
    merge_into_place_key: str | None = None


def load_overrides(path: Path | None) -> dict[str, Override]:
    """Parse an overrides JSONL into `{place_key: Override}`.

    `None` or a missing path yields `{}` — overrides are optional, and a
    site that has never needed one should not have to carry an empty
    file."""

    if path is None or not Path(path).exists():
        return {}

    out: dict[str, Override] = {}
    for lineno, raw in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), 1):
        raw = raw.strip()
        if not raw:
            continue
        try:
            row = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise OverrideError(f"{path}:{lineno} is not valid JSON: {exc}") from exc
        if not isinstance(row, dict):
            raise OverrideError(f"{path}:{lineno} is not a JSON object")
        if any(k.startswith(_DOC_PREFIX) for k in row):
            continue  # the file's own header/schema row

        place_key = row.get("place_key")
        action = row.get("action")
        if not place_key:
            raise OverrideError(f"{path}:{lineno} has no place_key")
        if action not in VALID_ACTIONS:
            raise OverrideError(
                f"{path}:{lineno} ({place_key}) has action {action!r}; expected one of {VALID_ACTIONS}"
            )
        if place_key in out:
            raise OverrideError(f"{path}:{lineno} duplicates place_key {place_key}")

        sources = tuple(row.get("sources") or ())
        lat, lng = row.get("lat"), row.get("lng")

        if action == "override":
            if lat is None or lng is None:
                raise OverrideError(f"{path}:{lineno} ({place_key}) is an override with no coordinate")
            if not sources:
                # The one hard rule of this package.
                raise OverrideError(
                    f"{path}:{lineno} ({place_key}) overrides a coordinate without citing a source; "
                    "an uncited coordinate cannot be told apart from a fabricated one"
                )
        if action == "merge_into" and not row.get("merge_into_place_key"):
            raise OverrideError(f"{path}:{lineno} ({place_key}) is merge_into with no merge_into_place_key")

        out[place_key] = Override(
            place_key=place_key,
            name=row.get("name") or "",
            action=action,
            lat=lat,
            lng=lng,
            confidence=float(row.get("confidence") or 0.0),
            sources=sources,
            note=row.get("note") or "",
            verified_on=row.get("verified_on"),
            merge_into_place_key=row.get("merge_into_place_key"),
        )
    return out
