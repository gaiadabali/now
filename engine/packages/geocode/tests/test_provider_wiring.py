"""Tests for `cli.build_provider` — the --provider/--chain wiring.

Kept separate from test_cli.py because these assert on the constructed
provider object rather than on a pipeline run, and none of them touch
the network: no OSM provider makes a call at construction time."""

from __future__ import annotations

import click
import pytest

from now_geocode.cli import CHAINABLE, build_provider
from now_geocode.providers.chain import ChainProvider
from now_geocode.providers.google import GoogleProvider
from now_geocode.providers.offline import OfflineProvider
from now_geocode.providers.osm import (
    NOMINATIM_PUBLIC_URL,
    PHOTON_PUBLIC_URL,
    NominatimProvider,
    PhotonProvider,
)


def test_none_stays_none():
    assert build_provider("none") is None


def test_offline_builds_offline():
    assert isinstance(build_provider("offline"), OfflineProvider)


def test_nominatim_defaults_to_the_public_instance_and_a_1s_throttle():
    provider = build_provider("nominatim")
    assert isinstance(provider, NominatimProvider)
    assert provider.base_url == NOMINATIM_PUBLIC_URL
    assert provider.min_interval_s == 1.0


def test_photon_defaults_to_the_public_instance():
    provider = build_provider("photon")
    assert isinstance(provider, PhotonProvider)
    assert provider.base_url == PHOTON_PUBLIC_URL


def test_self_hosting_overrides_url_and_throttle():
    provider = build_provider(
        "nominatim", osm_base_url="http://nominatim.internal:8080/", osm_min_interval=0.0
    )
    assert provider.base_url == "http://nominatim.internal:8080"  # trailing slash stripped
    assert provider.min_interval_s == 0.0


def test_custom_user_agent_is_passed_through():
    provider = build_provider("photon", osm_user_agent="now-engine/2.0 (+mailto:x@y.z)")
    assert provider.user_agent == "now-engine/2.0 (+mailto:x@y.z)"


def test_google_without_a_key_is_a_usage_error_that_points_at_the_free_option(monkeypatch):
    monkeypatch.delenv("GOOGLE_MAPS_API_KEY", raising=False)
    with pytest.raises(click.UsageError) as excinfo:
        build_provider("google")
    message = str(excinfo.value)
    assert "photon" in message or "nominatim" in message


def test_google_with_a_key_builds():
    provider = build_provider("google", google_api_key="k")
    assert isinstance(provider, GoogleProvider)


def test_default_chain_is_free_first_then_google():
    provider = build_provider("chain", google_api_key="k")
    assert isinstance(provider, ChainProvider)
    assert [p.name for p in provider.providers] == ["photon", "google"]


def test_chain_order_is_respected():
    provider = build_provider("chain", chain="nominatim,photon", google_api_key=None)
    assert [p.name for p in provider.providers] == ["nominatim", "photon"]


def test_an_all_free_chain_needs_no_google_key(monkeypatch):
    """The whole point of the exercise: a full run with zero spend."""
    monkeypatch.delenv("GOOGLE_MAPS_API_KEY", raising=False)
    provider = build_provider("chain", chain="photon,nominatim")
    assert provider.name == "chain(photon+nominatim)"


def test_chain_propagates_osm_settings_to_every_osm_member():
    provider = build_provider(
        "chain", chain="photon,nominatim", osm_base_url="http://osm.internal", osm_min_interval=0.0
    )
    for member in provider.providers:
        assert member.base_url == "http://osm.internal"
        assert member.min_interval_s == 0.0


def test_chain_rejects_unknown_provider_names():
    with pytest.raises(click.UsageError) as excinfo:
        build_provider("chain", chain="photon,mapbox")
    assert "mapbox" in str(excinfo.value)


def test_chain_rejects_none_and_offline_members():
    """Chaining a no-op does nothing; chaining the synthetic generator
    would smuggle fabricated points into a real run."""
    for bad in ("none", "offline"):
        with pytest.raises(click.UsageError):
            build_provider("chain", chain=f"photon,{bad}")
        assert bad not in CHAINABLE


def test_chain_rejects_a_duplicated_provider():
    with pytest.raises(click.UsageError):
        build_provider("chain", chain="photon,photon")


def test_empty_chain_is_rejected():
    with pytest.raises(click.UsageError):
        build_provider("chain", chain="  ,  ")


def test_chain_missing_google_key_still_raises_the_helpful_error(monkeypatch):
    monkeypatch.delenv("GOOGLE_MAPS_API_KEY", raising=False)
    with pytest.raises(click.UsageError):
        build_provider("chain", chain="photon,google")
