from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx
import pytest

from wp_harvest.client import HarvestError, RestClient
from wp_harvest.config import Config
from wp_harvest.runner import harvest_site
from wp_harvest.sink import read_jsonl

BASE = "https://example.test"


def make_config(tmp_path: Path, **kw: Any) -> Config:
    defaults: dict[str, Any] = {
        "per_page": 2,
        "delay_seconds": 0.0,
        "max_retries": 3,
        "timeout_seconds": 1.0,
    }
    defaults.update(kw)
    return Config.build("mysite", BASE, output_dir=tmp_path, **defaults)


def collection_transport(
    corpus: dict[str, list[dict[str, Any]]],
    per_page: int = 2,
    on_request: list[httpx.Request] | None = None,
) -> httpx.MockTransport:
    """A minimal stand-in for the WordPress collection endpoints."""

    def handler(request: httpx.Request) -> httpx.Response:
        if on_request is not None:
            on_request.append(request)
        endpoint = request.url.path.rsplit("/", 1)[-1]
        records = corpus.get(endpoint)
        if records is None:
            return httpx.Response(404, json={"code": "rest_no_route"})

        records = sorted(records, key=lambda r: r["id"])
        page = int(request.url.params.get("page", 1))
        total = len(records)
        total_pages = max(1, -(-total // per_page))
        if page > total_pages:
            return httpx.Response(
                400, content=b'{"code":"rest_post_invalid_page_number"}'
            )
        start = (page - 1) * per_page
        return httpx.Response(
            200,
            json=records[start : start + per_page],
            headers={"X-WP-Total": str(total), "X-WP-TotalPages": str(total_pages)},
        )

    return httpx.MockTransport(handler)


def client_for(config: Config, transport: httpx.MockTransport) -> RestClient:
    return RestClient(config, httpx.Client(transport=transport, base_url=BASE))


class TestRetry:
    def test_retries_then_succeeds(self, tmp_path: Path) -> None:
        attempts = {"n": 0}

        def handler(request: httpx.Request) -> httpx.Response:
            attempts["n"] += 1
            if attempts["n"] < 3:
                return httpx.Response(503)
            return httpx.Response(200, json={"ok": True})

        config = make_config(tmp_path)
        with client_for(config, httpx.MockTransport(handler)) as client:
            assert client.get_json(f"{BASE}/x") == {"ok": True}
        assert attempts["n"] == 3

    def test_gives_up_after_max_retries(self, tmp_path: Path) -> None:
        config = make_config(tmp_path, max_retries=2)
        transport = httpx.MockTransport(lambda r: httpx.Response(429))
        with client_for(config, transport) as client:
            with pytest.raises(HarvestError, match="HTTP 429"):
                client.get_json(f"{BASE}/x")
            assert client.retry_count == 1

    def test_a_404_is_not_retried(self, tmp_path: Path) -> None:
        calls = {"n": 0}

        def handler(request: httpx.Request) -> httpx.Response:
            calls["n"] += 1
            return httpx.Response(404)

        config = make_config(tmp_path)
        with client_for(config, httpx.MockTransport(handler)) as client:
            assert client.get(f"{BASE}/x").status_code == 404
        assert calls["n"] == 1, "a real answer must not be hammered"

    def test_a_timeout_is_retried(self, tmp_path: Path) -> None:
        attempts = {"n": 0}

        def handler(request: httpx.Request) -> httpx.Response:
            attempts["n"] += 1
            if attempts["n"] == 1:
                raise httpx.ReadTimeout("slow", request=request)
            return httpx.Response(200, json=[])

        config = make_config(tmp_path)
        with client_for(config, httpx.MockTransport(handler)) as client:
            assert client.get_json(f"{BASE}/x") == []
        assert attempts["n"] == 2

    def test_non_json_is_an_error_not_a_silent_empty(self, tmp_path: Path) -> None:
        transport = httpx.MockTransport(lambda r: httpx.Response(200, content=b"<html>"))
        with client_for(make_config(tmp_path), transport) as client:
            with pytest.raises(HarvestError, match="non-JSON"):
                client.get_json(f"{BASE}/x")


class TestPagination:
    def test_walks_every_page_exactly_once(self, tmp_path: Path) -> None:
        corpus = {"posts": [{"id": i} for i in range(1, 8)]}
        config = make_config(tmp_path)
        with client_for(config, collection_transport(corpus)) as client:
            seen = [r["id"] for _, records, _ in client.paginate("posts") for r in records]
        assert seen == list(range(1, 8))

    def test_orders_by_ascending_id(self, tmp_path: Path) -> None:
        """Stable pagination: the WP default (date desc) reshuffles mid-run."""
        requests: list[httpx.Request] = []
        corpus = {"posts": [{"id": i} for i in range(1, 4)]}
        config = make_config(tmp_path)
        transport = collection_transport(corpus, on_request=requests)
        with client_for(config, transport) as client:
            list(client.paginate("posts"))
        assert requests[0].url.params["orderby"] == "id"
        assert requests[0].url.params["order"] == "asc"

    def test_an_empty_collection_yields_nothing(self, tmp_path: Path) -> None:
        config = make_config(tmp_path)
        with client_for(config, collection_transport({"posts": []})) as client:
            assert list(client.paginate("posts")) == []

    def test_walking_off_the_end_is_not_an_error(self, tmp_path: Path) -> None:
        config = make_config(tmp_path)
        with client_for(config, collection_transport({"posts": [{"id": 1}]})) as client:
            result = client.page("posts", 9)
        assert result.records == []

    def test_total_reads_the_header_without_downloading(self, tmp_path: Path) -> None:
        corpus = {"media": [{"id": i} for i in range(1, 31)]}
        config = make_config(tmp_path)
        with client_for(config, collection_transport(corpus)) as client:
            assert client.total("media") == 30
            assert client.request_count == 1


class TestHarvestSite:
    def test_end_to_end_writes_projected_rows(self, tmp_path: Path) -> None:
        corpus = {
            "categories": [
                {"id": 3, "taxonomy": "category", "name": "News", "slug": "news", "count": 2}
            ],
            "tags": [
                {"id": 11, "taxonomy": "post_tag", "name": "Hotels", "slug": "hotels", "count": 1}
            ],
            "posts": [
                {
                    "id": 100,
                    "type": "post",
                    "status": "publish",
                    "title": {"rendered": "A &amp; B"},
                    "content": {"rendered": "<p>x</p>"},
                    "link": f"{BASE}/a-b/",
                    "categories": [3],
                    "tags": [11],
                }
            ],
        }
        config = make_config(tmp_path)
        with client_for(config, collection_transport(corpus)) as client:
            results = harvest_site(
                config, ["categories", "tags", "posts"], client=client
            )

        by_key = {r.key: r for r in results}
        assert all(r.complete for r in results)
        post = read_jsonl(by_key["posts"].path)[0]
        assert post["title"] == "A & B"
        assert post["categories"] == ["News"], "term names must resolve"
        assert post["tags"] == ["Hotels"]

    def test_terms_are_read_from_disk_when_not_reselected(self, tmp_path: Path) -> None:
        """Harvesting only posts must not silently emit empty category lists."""
        config = make_config(tmp_path)
        (tmp_path / "categories.jsonl").write_text(
            json.dumps({"term_id": 3, "name": "News"}) + "\n", encoding="utf-8"
        )
        corpus = {
            "posts": [
                {
                    "id": 100,
                    "type": "post",
                    "status": "publish",
                    "title": {"rendered": "T"},
                    "content": {"rendered": "x"},
                    "categories": [3],
                }
            ]
        }
        with client_for(config, collection_transport(corpus)) as client:
            results = harvest_site(config, ["posts"], client=client)
        assert read_jsonl(results[0].path)[0]["categories"] == ["News"]

    def test_incomplete_is_reported_when_rows_are_short(self, tmp_path: Path) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            if int(request.url.params.get("page", 1)) == 1:
                return httpx.Response(
                    200,
                    json=[{"id": 1, "taxonomy": "category", "name": "A", "slug": "a"}],
                    headers={"X-WP-Total": "50", "X-WP-TotalPages": "1"},
                )
            return httpx.Response(400, content=b'{"code":"rest_post_invalid_page_number"}')

        config = make_config(tmp_path)
        with client_for(config, httpx.MockTransport(handler)) as client:
            results = harvest_site(config, ["categories"], client=client)
        result = results[0]
        assert result.unique_ids == 1
        assert result.reported_total == 50
        assert not result.complete

    def test_a_row_published_mid_harvest_does_not_read_as_failure(
        self, tmp_path: Path
    ) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            if int(request.url.params.get("page", 1)) == 1:
                return httpx.Response(
                    200,
                    json=[
                        {"id": 1, "taxonomy": "category", "name": "A", "slug": "a"},
                        {"id": 2, "taxonomy": "category", "name": "B", "slug": "b"},
                    ],
                    headers={"X-WP-Total": "1", "X-WP-TotalPages": "1"},
                )
            return httpx.Response(400, content=b'{"code":"rest_post_invalid_page_number"}')

        config = make_config(tmp_path)
        with client_for(config, httpx.MockTransport(handler)) as client:
            results = harvest_site(config, ["categories"], client=client)
        assert results[0].complete

    def test_media_rows_carry_match_keys(self, tmp_path: Path) -> None:
        corpus = {
            "media": [
                {
                    "id": 1,
                    "source_url": f"{BASE}/wp-content/uploads/2020/01/a-150x150.jpg",
                    "mime_type": "image/jpeg",
                    "media_details": {"file": "2020/01/a-150x150.jpg", "sizes": {}},
                }
            ]
        }
        config = make_config(tmp_path)
        with client_for(config, collection_transport(corpus)) as client:
            results = harvest_site(config, ["media"], client=client)
        row = read_jsonl(results[0].path)[0]
        assert "a.jpg" in row["match_keys"]


class TestCheckUrlsAccounting:
    def test_url_checks_are_counted_as_requests(self, tmp_path: Path) -> None:
        """The report prints request_count, so it must include these."""
        from wp_harvest.verify import check_urls

        transport = httpx.MockTransport(lambda r: httpx.Response(301))
        with client_for(make_config(tmp_path), transport) as client:
            check_urls(client, [f"{BASE}/a", f"{BASE}/b"], delay=0.0)
            assert client.request_count == 2

    def test_head_rejection_falls_back_to_get(self, tmp_path: Path) -> None:
        """Static files on this host reject HEAD; that is not a broken URL."""
        from wp_harvest.verify import check_urls

        methods: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            methods.append(request.method)
            return httpx.Response(405 if request.method == "HEAD" else 200)

        with client_for(make_config(tmp_path), httpx.MockTransport(handler)) as client:
            results = check_urls(client, [f"{BASE}/img.jpg"], delay=0.0)
        assert methods == ["HEAD", "GET"]
        assert results[0].outcome == "ok"
        assert client.request_count == 2

    def test_a_redirect_records_the_first_hop_not_the_destination(
        self, tmp_path: Path
    ) -> None:
        from wp_harvest.verify import check_urls

        transport = httpx.MockTransport(
            lambda r: httpx.Response(301, headers={"Location": f"{BASE}/new/"})
        )
        with client_for(make_config(tmp_path), transport) as client:
            results = check_urls(client, [f"{BASE}/old/"], delay=0.0)
        assert results[0].outcome == "redirect"
        assert results[0].final_url == f"{BASE}/new/"

    def test_a_transport_error_is_recorded_not_raised(self, tmp_path: Path) -> None:
        from wp_harvest.verify import check_urls, summarise

        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("refused", request=request)

        with client_for(make_config(tmp_path), httpx.MockTransport(handler)) as client:
            results = check_urls(client, [f"{BASE}/a"], delay=0.0)
        assert results[0].outcome == "error"
        assert summarise(results) == {"error": 1, "total": 1}
