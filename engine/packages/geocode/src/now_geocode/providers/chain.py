"""`ChainProvider` — try providers in order, first real answer wins.

The point of this class is the measured-not-assumed rollout described in
`README.md`: put a free OSM provider in front of Google, run the batch,
and read off the report how much the free rung actually covered. Google
is then billed only for the residue OSM could not resolve, and the same
`geocoded_places.jsonl` contract comes out either way.

    ChainProvider([PhotonProvider(), GoogleProvider()])

Composition is per *call*, not per run: rung 2 might be answered by
Photon for one candidate and by Google for the next. `ladder.py` is
untouched — this satisfies the same two-method `GeocodeProvider`
Protocol as every other provider.

## Error semantics — the part that matters

Naively "try each, return the first non-None" is wrong, because the
three outcomes a provider can produce are not interchangeable:

| outcome                | meaning                        | chain does          |
|------------------------|--------------------------------|---------------------|
| `ProviderResult`       | found it                       | return it, stop     |
| `None`                 | queried, genuinely nothing     | try the next        |
| `RetryableProviderError` | the call never happened      | try next, but remember |
| `ProviderConfigError`  | this provider is unusable      | disable it for the run |

The load-bearing rule is the third row. **A retryable failure must never
be reported to the ladder as `None`.** `None` is a *stable negative*:
`state.py` caches it as final and no future run will re-ask. So if
Photon rate-limits and Google then legitimately returns nothing, the
chain re-raises the retryable error rather than returning `None` — the
candidate stays not-final and the next run re-walks it. Silently
downgrading a transient failure into a permanent "this place does not
exist" is precisely the kind of quiet data loss that only surfaces
months later as an unexplained coverage hole.

`ProviderConfigError` is treated as a property of the *provider*, not of
the call — a missing API key or a 403 will not fix itself mid-run, so
the provider is dropped for the remainder of the run instead of raising
on every one of the remaining candidates. If that leaves the chain with
no usable providers at all, the error is re-raised: a chain that can
never resolve anything is a configuration failure, not a run that should
grind through thousands of candidates producing nothing.
"""

from __future__ import annotations

from typing import Any, Callable

from now_geocode.models import ProviderResult
from now_geocode.providers.base import (
    GeocodeProvider,
    ProviderConfigError,
    RetryableProviderError,
)


class ChainProvider:
    """Ordered fallback across several providers. Satisfies
    `GeocodeProvider`, so `ladder.py` cannot tell it from a single one."""

    def __init__(self, providers: list[GeocodeProvider], *, on_event: Any = None) -> None:
        if not providers:
            raise ValueError("ChainProvider needs at least one provider")
        self.providers = list(providers)
        # Optional observability hook: called as on_event(kind, provider_name, detail).
        # The CLI passes a echo-to-stderr callback so a long batch shows
        # which rung of the chain is actually doing the work.
        self._on_event = on_event
        self._disabled: dict[str, str] = {}

    @property
    def name(self) -> str:
        return "chain(" + "+".join(p.name for p in self.providers) + ")"

    @property
    def disabled(self) -> dict[str, str]:
        """provider name -> why it was dropped. Surfaced in the run summary."""
        return dict(self._disabled)

    def geocode_address(self, address: str) -> ProviderResult | None:
        return self._walk(lambda p: p.geocode_address(address), "geocode_address")

    def find_place(self, name: str, context: str | None) -> ProviderResult | None:
        return self._walk(lambda p: p.find_place(name, context), "find_place")

    def _walk(
        self,
        call: Callable[[GeocodeProvider], ProviderResult | None],
        operation: str,
    ) -> ProviderResult | None:
        retryable: Exception | None = None
        config_error: Exception | None = None
        attempted = 0

        for provider in self.providers:
            if provider.name in self._disabled:
                continue
            attempted += 1
            try:
                result = call(provider)
            except RetryableProviderError as exc:
                # Transient. Remember it — it changes what a later `None`
                # is allowed to mean (see the module docstring).
                retryable = exc
                self._emit("retryable", provider.name, f"{operation}: {exc}")
                continue
            except ProviderConfigError as exc:
                # Structural. This provider is done for the whole run.
                config_error = exc
                self._disabled[provider.name] = str(exc)
                self._emit("disabled", provider.name, f"{operation}: {exc}")
                continue

            if result is not None:
                self._emit("resolved", provider.name, operation)
                return result
            # A clean zero-result: this provider genuinely has nothing.
            self._emit("miss", provider.name, operation)

        if attempted == 0:
            # Every provider was disabled by an earlier call. The chain
            # cannot resolve anything ever again — fail loudly.
            raise ProviderConfigError(
                "every provider in the chain has been disabled: "
                + "; ".join(f"{n}: {why}" for n, why in self._disabled.items())
            )
        if retryable is not None:
            # At least one provider never actually got to answer. Do not
            # let the ladder cache this as a stable negative.
            raise retryable
        if config_error is not None and len(self._disabled) == len(self.providers):
            raise config_error
        return None

    def _emit(self, kind: str, provider_name: str, detail: str) -> None:
        if self._on_event is not None:
            self._on_event(kind, provider_name, detail)
