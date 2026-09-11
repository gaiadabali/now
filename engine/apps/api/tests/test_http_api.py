from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.main import create_app

from tests.conftest import make_test_settings


@pytest.fixture
def client() -> Iterator[TestClient]:
    settings = make_test_settings()
    app = create_app(settings)
    with TestClient(app) as c:
        yield c


def test_healthz_is_unauthenticated_and_touches_no_db(client: TestClient) -> None:
    resp = client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_city_health_resolves_correct_database(client: TestClient) -> None:
    resp = client.get("/v1/alpha/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["site"] == "alpha"
    assert body["status"] == "ok"
    assert body["database"] == "reachable"
    assert isinstance(body["latency_ms"], (int, float))


def test_second_city_health_is_independent(client: TestClient) -> None:
    resp = client.get("/v1/beta/health")
    assert resp.status_code == 200
    assert resp.json()["site"] == "beta"


def test_unknown_site_is_404_not_500(client: TestClient) -> None:
    resp = client.get("/v1/does-not-exist/health")
    assert resp.status_code == 404
    assert "unknown site" in resp.json()["detail"]


def test_provisioning_site_is_404(client: TestClient) -> None:
    """A registered-but-not-active site is not yet a valid routing target."""
    resp = client.get("/v1/gamma-provisioning/health")
    assert resp.status_code == 404


def test_site_with_unreachable_database_is_503_with_useful_message(client: TestClient) -> None:
    resp = client.get("/v1/delta-unreachable/health")
    assert resp.status_code == 503
    assert "temporarily unavailable" in resp.json()["detail"]


def test_repeated_calls_to_unreachable_site_keep_returning_503(client: TestClient) -> None:
    """Guards against the pool cache being poisoned into a permanently
    broken or ever-growing state by a prior failure."""
    first = client.get("/v1/delta-unreachable/health")
    second = client.get("/v1/delta-unreachable/health")
    assert first.status_code == 503
    assert second.status_code == 503


def test_request_id_header_present_on_every_response(client: TestClient) -> None:
    resp = client.get("/v1/alpha/health")
    assert "x-request-id" in resp.headers

    healthz_resp = client.get("/healthz")
    assert "x-request-id" in healthz_resp.headers


def test_openapi_schema_exposes_health_route(client: TestClient) -> None:
    schema = client.get("/openapi.json").json()
    assert "/v1/{site}/health" in schema["paths"]
    assert "/healthz" in schema["paths"]
