"""Unit tests for ChainProvider. The interesting cases are all about
error semantics, not happy-path fallthrough: the chain must never let a
transient failure reach the ladder as a stable negative, because
state.py caches negatives as final and no later run would re-ask."""

from __future__ import annotations

import pytest

from now_geocode.models import ProviderResult
from now_geocode.providers.base import ProviderConfigError, RetryableProviderError
from now_geocode.providers.chain import ChainProvider


def make_result(provider_name: str) -> ProviderResult:
    return ProviderResult(
        lat=-8.68,
        lng=115.15,
        formatted_address="somewhere",
        google_place_id=None,
        location_type="osm_poi",
        confidence=0.9,
        provider=provider_name,
        is_synthetic=False,
        raw={},
    )


class StubProvider:
    """Configurable provider. `behaviour` is what each call does:
    a ProviderResult, None, or an exception instance to raise."""

    def __init__(self, name: str, behaviour):
        self.name = name
        self.behaviour = behaviour
        self.calls = 0

    def _act(self):
        self.calls += 1
        if isinstance(self.behaviour, Exception):
            raise self.behaviour
        return self.behaviour

    def geocode_address(self, address: str):
        return self._act()

    def find_place(self, name: str, context: str | None):
        return self._act()


def test_first_provider_wins_and_second_is_never_called():
    a = StubProvider("a", make_result("a"))
    b = StubProvider("b", make_result("b"))
    chain = ChainProvider([a, b])
    result = chain.geocode_address("x")
    assert result.provider == "a"
    assert b.calls == 0


def test_falls_through_a_clean_miss_to_the_next_provider():
    a = StubProvider("a", None)
    b = StubProvider("b", make_result("b"))
    chain = ChainProvider([a, b])
    result = chain.geocode_address("x")
    assert result.provider == "b"
    assert a.calls == 1


def test_all_clean_misses_returns_none():
    """Every provider genuinely queried and found nothing — that IS a
    stable negative and is allowed to be cached as final."""
    chain = ChainProvider([StubProvider("a", None), StubProvider("b", None)])
    assert chain.geocode_address("x") is None


def test_retryable_then_success_returns_the_success():
    a = StubProvider("a", RetryableProviderError("429"))
    b = StubProvider("b", make_result("b"))
    chain = ChainProvider([a, b])
    assert chain.geocode_address("x").provider == "b"


def test_retryable_then_miss_reraises_rather_than_returning_none():
    """The load-bearing rule. Provider 'a' never actually answered, so
    'b' finding nothing does not prove the place is unfindable. Returning
    None here would poison the state cache with a permanent negative."""
    a = StubProvider("a", RetryableProviderError("429 rate limited"))
    b = StubProvider("b", None)
    chain = ChainProvider([a, b])
    with pytest.raises(RetryableProviderError):
        chain.geocode_address("x")


def test_config_error_disables_that_provider_for_the_whole_run():
    a = StubProvider("a", ProviderConfigError("no api key"))
    b = StubProvider("b", make_result("b"))
    chain = ChainProvider([a, b])

    chain.geocode_address("first")
    chain.geocode_address("second")
    chain.geocode_address("third")

    # 'a' was tried once, then dropped — not re-attempted on every candidate.
    assert a.calls == 1
    assert b.calls == 3
    assert "a" in chain.disabled


def test_config_error_on_every_provider_raises():
    a = StubProvider("a", ProviderConfigError("no key"))
    b = StubProvider("b", ProviderConfigError("also no key"))
    chain = ChainProvider([a, b])
    with pytest.raises(ProviderConfigError):
        chain.geocode_address("x")


def test_chain_with_everything_disabled_fails_loudly_on_the_next_call():
    """A chain that can never resolve anything is a configuration
    failure, not a run that should grind through thousands of candidates
    producing nothing."""
    a = StubProvider("a", ProviderConfigError("no key"))
    chain = ChainProvider([a])
    with pytest.raises(ProviderConfigError):
        chain.geocode_address("first")
    with pytest.raises(ProviderConfigError) as excinfo:
        chain.geocode_address("second")
    assert "every provider in the chain has been disabled" in str(excinfo.value)
    assert a.calls == 1  # not re-attempted


def test_find_place_uses_the_same_semantics():
    a = StubProvider("a", RetryableProviderError("boom"))
    b = StubProvider("b", None)
    chain = ChainProvider([a, b])
    with pytest.raises(RetryableProviderError):
        chain.find_place("Potato Head", "Bali")


def test_name_reports_the_composition():
    chain = ChainProvider([StubProvider("photon", None), StubProvider("google", None)])
    assert chain.name == "chain(photon+google)"


def test_events_report_which_provider_did_the_work():
    events = []
    a = StubProvider("a", None)
    b = StubProvider("b", make_result("b"))
    chain = ChainProvider([a, b], on_event=lambda k, p, d: events.append((k, p)))
    chain.geocode_address("x")
    assert ("miss", "a") in events
    assert ("resolved", "b") in events


def test_empty_chain_is_rejected_at_construction():
    with pytest.raises(ValueError):
        ChainProvider([])


def test_satisfies_the_geocode_provider_protocol():
    """ladder.py must not be able to tell a chain from a single provider."""
    chain = ChainProvider([StubProvider("a", None)])
    assert hasattr(chain, "name")
    assert callable(chain.geocode_address)
    assert callable(chain.find_place)
