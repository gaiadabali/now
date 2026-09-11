"""The resolved outcome of one mention -> partnership lookup.

`LinkDecision.rel` is deliberately **not a constructor field**. If it
were, any caller (a bug, a future refactor, a `link_policy` value copied
in carelessly) could construct a paid-tier decision with `rel=None` or
`rel="nofollow"` and the renderer would happily emit it -- exactly the
failure mode E1.5 measured live: 9,128 of 9,135 external links (99.9%)
carry no `rel` at all. Instead `rel` is a `@property` computed purely
from `tier`: for `tier == "paid"` it can only ever be `"sponsored"`,
for every other tier it is `None` (nothing to omit -- there is no link).
There is no code path, including `dataclasses.replace()`, that produces a
`LinkDecision` with a different `rel` for a paid tier, because no such
field exists to set. See `tests/test_rel_sponsored.py` for the ways this
is attacked.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

Tier = Literal["free", "listed", "paid"]

_VALID_TIERS = ("free", "listed", "paid")


@dataclass(frozen=True)
class LinkDecision:
    """One mention's resolved rendering instruction.

    `place_id` is the mention's subject (always present). `partnership_id`/
    `org_id` are None when no partnership was found at all (bare `free`
    with nothing to attribute). `slug` is required for `listed` (the
    internal `/places/{slug}` target) and optional otherwise.
    """

    tier: Tier
    place_id: str
    slug: str | None = None
    partnership_id: str | None = None
    org_id: str | None = None
    external_url: str | None = None
    show_badge: bool = False
    badge_label: str | None = None
    utm_template: str | None = None
    resolved_via: Literal["place", "org", "none"] = "none"

    def __post_init__(self) -> None:
        if self.tier not in _VALID_TIERS:
            raise ValueError(f"invalid tier {self.tier!r}, must be one of {_VALID_TIERS}")
        if self.tier == "listed" and not self.slug:
            raise ValueError("listed tier requires a slug (internal /places/{slug} target)")
        if self.tier == "paid" and not self.external_url:
            raise ValueError("paid tier requires an external_url")

    @property
    def rel(self) -> str | None:
        """`"sponsored"` for paid, `None` otherwise. Computed, not settable --
        see module docstring. This is the one line E4.2 exists to guarantee."""
        return "sponsored" if self.tier == "paid" else None

    @property
    def href(self) -> str | None:
        if self.tier == "paid":
            return self.external_url
        if self.tier == "listed":
            return f"/places/{self.slug}"
        return None

    @property
    def is_link(self) -> bool:
        return self.tier in ("listed", "paid")
