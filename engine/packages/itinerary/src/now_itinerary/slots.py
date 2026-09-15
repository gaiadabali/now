"""§12 step 3's slot ladder: breakfast → morning → lunch → afternoon →
dinner → night.

These defaults are a **starting point, not a law**. Per §3.5 the only
legitimate home for a per-city difference is configuration, and meal
times genuinely differ by city -- a Bali night slot runs later than
Jakarta's. `sites.itinerary_slots` overrides this table without a
deploy, the same mechanism `sites.ranking_weights` gives the blender.
`load_slot_specs` is the seam that reads it.

**`eligible_types` is a whitelist, and `stay` is in none of them.** A
hotel is where the visitor sleeps, not a stop on the day's route; putting
one in an afternoon slot would be the itinerary equivalent of the
competitor-filter bug. Accommodation belongs to the trip, not the
timeline, and modelling it as a stop is left out deliberately rather than
forgotten.
"""

from __future__ import annotations

from now_itinerary.models import Slot, SlotSpec

MEAL_TYPES = frozenset({"eat"})
DRINK_TYPES = frozenset({"drink", "eat"})
ACTIVITY_TYPES = frozenset({"do", "culture", "shop", "wellness"})


def _hm(hour: int, minute: int = 0) -> int:
    return hour * 60 + minute


DEFAULT_SLOT_SPECS: tuple[SlotSpec, ...] = (
    SlotSpec(Slot.BREAKFAST, _hm(7), _hm(10), MEAL_TYPES),
    SlotSpec(Slot.MORNING, _hm(10), _hm(12, 30), ACTIVITY_TYPES),
    # Lunch and dinner are the two slots a day is actually built around;
    # an itinerary that skips a meal is a bug report, not a preference.
    SlotSpec(Slot.LUNCH, _hm(12), _hm(14, 30), MEAL_TYPES, required=True),
    SlotSpec(Slot.AFTERNOON, _hm(14, 30), _hm(18), ACTIVITY_TYPES),
    SlotSpec(Slot.DINNER, _hm(18), _hm(21), MEAL_TYPES, required=True),
    SlotSpec(Slot.NIGHT, _hm(21), _hm(24), DRINK_TYPES),
)


def load_slot_specs(override: dict | None = None) -> tuple[SlotSpec, ...]:
    """Merges a `sites.itinerary_slots` JSON override over the defaults.

    Partial by design: an override naming only `night` keeps every other
    slot's default rather than requiring a city to restate the whole
    ladder to move one window. Unknown slot names raise -- a typo that
    silently did nothing would be indistinguishable from an override that
    worked.
    """
    if not override:
        return DEFAULT_SLOT_SPECS

    by_name = {spec.slot.value: spec for spec in DEFAULT_SLOT_SPECS}
    for name, cfg in override.items():
        if name not in by_name:
            raise ValueError(
                f"unknown itinerary slot {name!r}; expected one of {sorted(by_name)}"
            )
        base = by_name[name]
        by_name[name] = SlotSpec(
            slot=base.slot,
            window_start=cfg.get("window_start", base.window_start),
            window_end=cfg.get("window_end", base.window_end),
            eligible_types=frozenset(cfg.get("eligible_types", base.eligible_types)),
            required=cfg.get("required", base.required),
        )
    return tuple(sorted(by_name.values(), key=lambda s: s.slot.order))
