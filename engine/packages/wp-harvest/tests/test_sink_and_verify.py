from __future__ import annotations

import json
from pathlib import Path

import pytest

from wp_harvest.config import Config, ConfigError
from wp_harvest.sink import ResumableSink, read_jsonl
from wp_harvest.verify import compare_to_sitemap, normalise


class TestResumableSink:
    def test_writes_jsonl_and_advances_the_cursor(self, tmp_path: Path) -> None:
        path = tmp_path / "out.jsonl"
        with ResumableSink(path, "posts") as sink:
            sink.write_page(1, [{"wp_id": 1}, {"wp_id": 2}])
            sink.write_page(2, [{"wp_id": 3}])
        assert [r["wp_id"] for r in read_jsonl(path)] == [1, 2, 3]
        state = json.loads(sink.state_path.read_text(encoding="utf-8"))
        assert state == {
            "endpoint": "posts",
            "last_completed_page": 2,
            "records_written": 3,
        }

    def test_resume_continues_from_the_cursor(self, tmp_path: Path) -> None:
        path = tmp_path / "out.jsonl"
        with ResumableSink(path, "posts") as sink:
            sink.write_page(1, [{"wp_id": 1}])
            sink.write_page(2, [{"wp_id": 2}])

        with ResumableSink(path, "posts", resume=True) as sink:
            assert sink.start_page == 3
            sink.write_page(3, [{"wp_id": 3}])
        assert [r["wp_id"] for r in read_jsonl(path)] == [1, 2, 3]

    def test_restart_truncates(self, tmp_path: Path) -> None:
        path = tmp_path / "out.jsonl"
        with ResumableSink(path, "posts") as sink:
            sink.write_page(1, [{"wp_id": 1}])
        with ResumableSink(path, "posts", resume=False) as sink:
            assert sink.start_page == 1
            sink.write_page(1, [{"wp_id": 9}])
        assert [r["wp_id"] for r in read_jsonl(path)] == [9]

    def test_resume_discards_a_partial_tail(self, tmp_path: Path) -> None:
        """A crash between fsync and the cursor write leaves extra lines."""
        path = tmp_path / "out.jsonl"
        with ResumableSink(path, "posts") as sink:
            sink.write_page(1, [{"wp_id": 1}])
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps({"wp_id": 2}) + "\n")
            handle.write('{"wp_id": 3, partial\n')

        with ResumableSink(path, "posts", resume=True) as sink:
            assert sink.start_page == 2
            sink.write_page(2, [{"wp_id": 2}])
        assert [r["wp_id"] for r in read_jsonl(path)] == [1, 2]

    def test_resume_after_an_endpoint_change_starts_over(self, tmp_path: Path) -> None:
        path = tmp_path / "out.jsonl"
        with ResumableSink(path, "posts") as sink:
            sink.write_page(1, [{"wp_id": 1}])
        with ResumableSink(path, "media", resume=True) as sink:
            assert sink.start_page == 1
        assert read_jsonl(path) == []

    def test_resume_with_no_prior_state_starts_at_one(self, tmp_path: Path) -> None:
        with ResumableSink(tmp_path / "fresh.jsonl", "posts", resume=True) as sink:
            assert sink.start_page == 1

    def test_corrupt_state_file_starts_over(self, tmp_path: Path) -> None:
        path = tmp_path / "out.jsonl"
        with ResumableSink(path, "posts") as sink:
            sink.write_page(1, [{"wp_id": 1}])
        sink.state_path.write_text("{not json", encoding="utf-8")
        with ResumableSink(path, "posts", resume=True) as sink:
            assert sink.start_page == 1

    def test_discard_state_removes_the_cursor(self, tmp_path: Path) -> None:
        path = tmp_path / "out.jsonl"
        with ResumableSink(path, "posts") as sink:
            sink.write_page(1, [{"wp_id": 1}])
            sink.discard_state()
        assert not sink.state_path.exists()

    def test_non_ascii_survives_a_round_trip(self, tmp_path: Path) -> None:
        path = tmp_path / "out.jsonl"
        with ResumableSink(path, "posts") as sink:
            sink.write_page(1, [{"title": "Nasi Gorèng – Kuta’s best"}])
        assert read_jsonl(path)[0]["title"] == "Nasi Gorèng – Kuta’s best"


class TestNormalise:
    @pytest.mark.parametrize(
        "url",
        [
            "https://www.example.test/a-post/",
            "http://example.test/a-post",
            "https://example.test/A-Post/",
            "https://www.example.test/a-post/?utm_source=x",
        ],
    )
    def test_equivalent_forms_collapse(self, url: str) -> None:
        assert normalise(url) == "example.test/a-post"

    def test_root_is_preserved(self) -> None:
        assert normalise("https://www.example.test/") == "example.test/"

    def test_different_paths_stay_different(self) -> None:
        assert normalise("https://example.test/a") != normalise("https://example.test/b")


class TestCompareToSitemap:
    def test_reports_matches_and_both_differences(self) -> None:
        result = compare_to_sitemap(
            ["https://www.example.test/a/", "https://www.example.test/gone/"],
            ["http://example.test/a", "https://example.test/new/"],
        )
        assert result["stored"] == 2
        assert result["live"] == 2
        assert result["matched"] == 1
        assert result["missing_from_sitemap"] == ["https://www.example.test/gone/"]
        assert result["not_in_stored_map"] == ["https://example.test/new/"]

    def test_duplicate_stored_urls_are_counted_once(self) -> None:
        result = compare_to_sitemap(
            ["https://example.test/a", "https://www.example.test/a/"],
            ["https://example.test/a"],
        )
        assert result["stored"] == 1
        assert result["matched"] == 1

    def test_empty_inputs_are_not_an_error(self) -> None:
        result = compare_to_sitemap([], [])
        assert result["stored"] == 0
        assert result["matched"] == 0


class TestConfig:
    def test_base_url_from_the_environment(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("WP_HARVEST_BASE_URL_MYSITE", "https://example.test/")
        config = Config.build("mysite")
        assert config.base_url == "https://example.test"
        assert config.api_root == "https://example.test/wp-json/wp/v2"

    def test_explicit_base_url_wins(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("WP_HARVEST_BASE_URL_MYSITE", "https://env.test")
        assert Config.build("mysite", "https://flag.test").base_url == "https://flag.test"

    def test_hyphens_map_to_underscores_in_the_env_key(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("WP_HARVEST_BASE_URL_MY_SITE", "https://example.test")
        assert Config.build("my-site").base_url == "https://example.test"

    def test_no_base_url_anywhere_is_an_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("WP_HARVEST_BASE_URL_MYSITE", raising=False)
        with pytest.raises(ConfigError, match="No base URL"):
            Config.build("mysite")

    def test_a_relative_base_url_is_rejected(self) -> None:
        with pytest.raises(ConfigError, match="absolute"):
            Config.build("mysite", "example.test")

    @pytest.mark.parametrize("slug", ["", "Bad", "9lives", "has space", "a" * 65])
    def test_bad_slugs_are_rejected(self, slug: str) -> None:
        with pytest.raises(ConfigError):
            Config.build(slug, "https://example.test")

    def test_output_dir_derives_from_the_slug(self) -> None:
        config = Config.build("mysite", "https://example.test")
        assert config.output_dir.parts[-3:] == ("mysite", "content", "harvested")


class TestRelativeUrlComparison:
    """The permalink map stores paths; the sitemap stores absolute URLs."""

    def test_a_relative_path_matches_an_absolute_sitemap_url(self) -> None:
        from wp_harvest.verify import compare_to_sitemap as compare

        result = compare(
            ["/a-post/"],
            ["https://www.example.test/a-post/"],
            default_host="example.test",
        )
        assert result["matched"] == 1
        assert result["missing_from_sitemap"] == []

    def test_without_a_default_host_nothing_matches(self) -> None:
        from wp_harvest.verify import compare_to_sitemap as compare

        result = compare(["/a-post/"], ["https://www.example.test/a-post/"])
        assert result["matched"] == 0

    def test_an_absolute_stored_url_still_wins_over_the_default(self) -> None:
        assert normalise("https://other.test/x", "example.test") == "other.test/x"

    def test_host_of_strips_scheme_and_www(self) -> None:
        from wp_harvest.verify import host_of

        assert host_of("https://www.example.test") == "example.test"
        assert host_of("http://example.test/") == "example.test"
