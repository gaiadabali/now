"""Per-component score types -- the thing the acceptance criteria call
"per-component scores retained (not collapsed into one number) so the
Inspector can show the breakdown."

`ComponentScore` is deliberately field-for-field identical to
`now_inspector.models.ComponentExplained` (`key`, `label`, `value`,
`explanation`, `available`) -- not imported from it (this package does
not depend on `now-inspector`; that dependency would run backwards from
every other producer/consumer pair in this monorepo, where the display
layer depends on the data layer, never the reverse -- see
`now-inspector`'s own pyproject, which already depends on `now-search`)
but structurally compatible by construction, so wiring the Inspector's
`blend_components: list[ComponentExplained]` field up to this package's
real output later is a one-line `ComponentExplained(**dataclasses.asdict(c))`
per component, not a redesign.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ComponentScore:
    key: str
    label: str
    value: float | None
    weight: float
    explanation: str
    available: bool


@dataclass(frozen=True)
class BlendComponents:
    """Raw, not-yet-weighted inputs for one candidate -- everything
    `compute_blend` needs. `None` means genuinely unavailable for this
    candidate today (see each field's producer module for why), not
    zero."""

    semantic: float | None = None
    covis: float | None = None
    freshness: float | None = None
    quality: float | None = None
    geo: float | None = None
    promo: float | None = None
