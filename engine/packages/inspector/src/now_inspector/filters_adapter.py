"""Optional, defensive integration with `engine/packages/filters` (E3.2),
which is being built by another agent **concurrently with this ticket**
and may not exist, may not be importable, or may not yet expose a stable
API at any given moment this Inspector is run. Per the ticket brief:

    "Design for it, code defensively, and degrade gracefully if it isn't
    importable yet."

This module never raises out of `get_fallback_rungs()` -- any import
error, attribute error, or exception from the filters package itself is
caught and turned into an honest "not available" result so one flaky
dependency never takes the whole Inspector page down. It also never
guesses at rung numbers/labels: if the package is present but its API
shape doesn't match any of the candidate entry points tried below, that
is reported as "importable, but no compatible API found" rather than
silently faking a rung.

The package name/module path is a best-effort guess (`now_filters`,
matching this repo's `now_<pkg>` naming convention seen in
`now_search`/`now_quality`/`now_db`/`now_embeddings`) since the package
does not exist in the tree as of this ticket. When E3.2 lands, whoever
wires it in for real should replace `_TRY_ENTRY_POINTS` below with the
actual call it exposes -- the rest of this module (the defensive
wrapper, the FallbackRungInfo shape) should not need to change.
"""

from __future__ import annotations

import importlib
from dataclasses import dataclass

from now_inspector.models import FallbackRungInfo

RAILS = ("row1_complementary", "row2_nearby", "row3_similar", "search")

_FALLBACK_LADDER_LABELS = {
    1: "1. strict (all filters)",
    2: "2. widen radius",
    3: "3. drop open-now",
    4: "4. area -> district -> city",
    5: "5. drop freshness decay",
    6: "6. editorial fallback",
}


@dataclass(frozen=True)
class FiltersPackageStatus:
    importable: bool
    module_name: str
    detail: str


def probe() -> FiltersPackageStatus:
    """Is `now_filters` importable at all, right now, in this process?"""
    for module_name in ("now_filters", "now_filters.trace", "engine_filters"):
        try:
            importlib.import_module(module_name)
        except ImportError:
            continue
        except Exception as exc:  # pragma: no cover - defensive, see module docstring
            return FiltersPackageStatus(
                importable=False,
                module_name=module_name,
                detail=f"Found {module_name!r} but importing it raised {exc.__class__.__name__}: {exc}",
            )
        else:
            return FiltersPackageStatus(importable=True, module_name=module_name, detail="imported cleanly")
    return FiltersPackageStatus(
        importable=False,
        module_name="now_filters",
        detail="No importable filters package found on this interpreter (E3.2 not merged/installed "
        "yet, or not on this venv's path). Degrading: fallback-rung panel will show 'not available'.",
    )


def get_fallback_rungs(entity_ids: list[str]) -> dict[str, list[FallbackRungInfo]]:
    """Best-effort per-candidate, per-rail fallback rung lookup. Returns a
    dict keyed by entity_id; each value is one FallbackRungInfo per rail
    in `RAILS`. Never raises -- every failure mode collapses to
    `available=False` entries with an explanatory note, per the ticket's
    'degrades gracefully' requirement.
    """
    status = probe()
    if not status.importable:
        return {
            eid: [
                FallbackRungInfo(
                    rail=rail,
                    rung_reached=None,
                    rung_label=None,
                    available=False,
                    note=status.detail,
                )
                for rail in RAILS
            ]
            for eid in entity_ids
        }

    # The package imported, but we have no verified API contract to call
    # (it does not exist in this tree as of this ticket -- see module
    # docstring). Report that honestly rather than fabricating rungs.
    try:
        module = importlib.import_module(status.module_name)
        candidate_fns = [
            getattr(module, name, None)
            for name in ("fallback_rung", "get_fallback_rung", "rung_for", "trace_fallback")
        ]
        entry_point = next((fn for fn in candidate_fns if callable(fn)), None)
        if entry_point is None:
            raise AttributeError("no recognised fallback-rung entry point on now_filters")

        out: dict[str, list[FallbackRungInfo]] = {}
        for eid in entity_ids:
            rungs = []
            for rail in RAILS:
                try:
                    rung = entry_point(entity_id=eid, rail=rail)
                    rungs.append(
                        FallbackRungInfo(
                            rail=rail,
                            rung_reached=rung,
                            rung_label=_FALLBACK_LADDER_LABELS.get(rung, str(rung)),
                            available=True,
                            note="from now_filters",
                        )
                    )
                except Exception as exc:  # pragma: no cover - defensive
                    rungs.append(
                        FallbackRungInfo(
                            rail=rail,
                            rung_reached=None,
                            rung_label=None,
                            available=False,
                            note=f"now_filters call failed: {exc.__class__.__name__}: {exc}",
                        )
                    )
            out[eid] = rungs
        return out
    except Exception as exc:  # pragma: no cover - defensive
        detail = (
            f"now_filters is importable ({status.module_name}) but no compatible fallback-rung API "
            f"was found ({exc.__class__.__name__}: {exc}). Update now_inspector.filters_adapter's "
            "_TRY_ENTRY_POINTS / candidate_fns once E3.2's real API is known."
        )
        return {
            eid: [
                FallbackRungInfo(rail=rail, rung_reached=None, rung_label=None, available=False, note=detail)
                for rail in RAILS
            ]
            for eid in entity_ids
        }
