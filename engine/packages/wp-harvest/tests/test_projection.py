from __future__ import annotations

from wp_harvest.harvest import content, media

# A trimmed but faithful copy of a real response from the live site, kept so
# the projections are tested against WordPress's actual envelope shapes
# (``{"rendered": ...}``, ``media_details.sizes``) rather than a guess.
MEDIA_RECORD = {
    "id": 112712,
    "date": "2026-09-08T10:49:09",
    "date_gmt": "2026-09-08T03:49:09",
    "modified_gmt": "2026-09-08T03:49:09",
    "guid": {"rendered": "https://nj.gaiada.com/embro-ismaya-jpeg-6/"},
    "slug": "embro-ismaya",
    "title": {"rendered": "embro ismaya"},
    "author": 6232,
    "caption": {"rendered": "<p>On the rack</p>"},
    "alt_text": "  Embroidered shirt  ",
    "media_type": "image",
    "mime_type": "image/jpeg",
    "filename": "embro-ismaya.jpeg",
    "filesize": 70977,
    "post": 112707,
    "source_url": "https://www.example.test/wp-content/uploads/2026/09/embro-ismaya.jpeg",
    "media_details": {
        "width": 903,
        "height": 1600,
        "file": "2026/09/embro-ismaya.jpeg",
        "filesize": 70977,
        "image_meta": {"credit": " Jane Doe ", "copyright": ""},
        "sizes": {
            "thumbnail": {
                "file": "embro-ismaya-150x150.jpeg",
                "width": 150,
                "height": 150,
                "mime_type": "image/jpeg",
                "filesize": 6100,
                "source_url": "https://www.example.test/wp-content/uploads/2026/09/embro-ismaya-150x150.jpeg",
            },
            "full": {
                "file": "embro-ismaya.jpeg",
                "width": 903,
                "height": 1600,
                "mime_type": "image/jpeg",
                "filesize": 70977,
                "source_url": "https://www.example.test/wp-content/uploads/2026/09/embro-ismaya.jpeg",
            },
        },
    },
}


class TestMediaProjection:
    def test_maps_to_the_extract_shape(self) -> None:
        row = media.project(MEDIA_RECORD)
        assert row["wp_id"] == 112712
        assert row["file"] == "2026/09/embro-ismaya.jpeg"
        assert row["width"] == 903
        assert row["height"] == 1600
        assert row["parent_post_id"] == 112707
        assert row["mime"] == "image/jpeg"

    def test_url_is_source_url_not_guid(self) -> None:
        """F11: guid points at another host for ~20% of attachments."""
        row = media.project(MEDIA_RECORD)
        assert row["url"] == MEDIA_RECORD["source_url"]
        assert row["guid"] == "https://nj.gaiada.com/embro-ismaya-jpeg-6/"
        assert row["url"] != row["guid"]

    def test_strings_are_stripped_and_unwrapped(self) -> None:
        row = media.project(MEDIA_RECORD)
        assert row["alt"] == "Embroidered shirt"
        assert row["credit"] == "Jane Doe"
        assert row["copyright"] is None
        assert row["caption"] == "<p>On the rack</p>"

    def test_size_variants_are_captured(self) -> None:
        row = media.project(MEDIA_RECORD)
        names = [s["name"] for s in row["sizes"]]
        assert names == ["full", "thumbnail"]
        assert row["sizes"][1]["file"] == "embro-ismaya-150x150.jpeg"

    def test_missing_source_url_falls_back_to_guid(self) -> None:
        record = {**MEDIA_RECORD}
        del record["source_url"]
        row = media.project(record)
        assert row["url"] == "https://nj.gaiada.com/embro-ismaya-jpeg-6/"


class TestMatchKeys:
    def test_exact_path_comes_first(self) -> None:
        keys = media.match_keys(
            "https://www.example.test/wp-content/uploads/2026/09/a.jpg", "2026/09/a.jpg"
        )
        assert keys[0] == "/wp-content/uploads/2026/09/a.jpg"

    def test_strips_the_responsive_size_suffix(self) -> None:
        """F29: 3,359 refs were unmatched because of -150x150 style suffixes."""
        keys = media.match_keys(
            "https://www.example.test/wp-content/uploads/2026/09/a-150x150.jpg",
            "2026/09/a-150x150.jpg",
        )
        assert "a-150x150.jpg" in keys
        assert "a.jpg" in keys

    def test_strips_the_numbered_duplicate_suffix(self) -> None:
        keys = media.match_keys(
            "https://www.example.test/wp-content/uploads/2026/09/a-6.jpg", "2026/09/a-6.jpg"
        )
        assert "a.jpg" in keys

    def test_strips_both_suffixes_together(self) -> None:
        keys = media.match_keys(
            "https://www.example.test/wp-content/uploads/2026/09/a-6-150x150.jpg",
            "2026/09/a-6-150x150.jpg",
        )
        assert "a.jpg" in keys

    def test_percent_decodes_the_path(self) -> None:
        keys = media.match_keys(
            "https://www.example.test/wp-content/uploads/2026/09/a%20b.jpg", None
        )
        assert "/wp-content/uploads/2026/09/a b.jpg" in keys

    def test_keys_are_unique_and_ordered(self) -> None:
        keys = media.match_keys(
            "https://www.example.test/wp-content/uploads/2026/09/a.jpg", "2026/09/a.jpg"
        )
        assert len(keys) == len(set(keys))

    def test_handles_a_missing_url(self) -> None:
        assert media.match_keys(None, None) == []

    def test_handles_an_extensionless_filename(self) -> None:
        keys = media.match_keys("https://www.example.test/wp-content/uploads/x/README", None)
        assert "README" in keys


POST_RECORD = {
    "id": 100786,
    "type": "post",
    "status": "publish",
    "title": {"rendered": "IHG Hotels &amp; Resorts &#8211; Debut"},
    "content": {"rendered": "<p>rendered</p>", "protected": False},
    "excerpt": {"rendered": "<p>dek</p>"},
    "date": "2026-09-07T13:05:02",
    "modified": "2026-09-07T13:05:06",
    "author": 1,
    "link": "https://www.example.test/ihg-debut/",
    "slug": "ihg-debut",
    "categories": [3, 9999],
    "tags": [11],
    "meta": {"_acf_changed": False},
    "featured_media": 100789,
    "format": "standard",
}


class TestPostProjection:
    def test_maps_to_the_extract_shape(self) -> None:
        row = content.project_post(POST_RECORD, {3: "News"}, {11: "Hotels"})
        assert row["wp_id"] == 100786
        assert row["permalink"] == "https://www.example.test/ihg-debut/"
        assert row["thumbnail_id"] == 100789
        assert row["author_id"] == 1

    def test_title_is_html_decoded(self) -> None:
        row = content.project_post(POST_RECORD)
        assert row["title"] == "IHG Hotels & Resorts – Debut"

    def test_taxonomy_resolves_to_names_and_keeps_ids(self) -> None:
        row = content.project_post(POST_RECORD, {3: "News"}, {11: "Hotels"})
        assert row["categories"] == ["News"]
        assert row["tags"] == ["Hotels"]
        assert row["category_ids"] == [3, 9999]

    def test_unknown_term_id_is_dropped_from_names_not_invented(self) -> None:
        row = content.project_post(POST_RECORD, {3: "News"}, {})
        assert row["categories"] == ["News"]
        assert row["tags"] == []
        assert 9999 in row["category_ids"]

    def test_view_context_is_flagged_as_not_raw(self) -> None:
        row = content.project_post(POST_RECORD)
        assert row["content_is_raw"] is False
        assert row["content_html"] == "<p>rendered</p>"

    def test_edit_context_prefers_raw_and_flags_it(self) -> None:
        record = {
            **POST_RECORD,
            "content": {"rendered": "<p>rendered</p>", "raw": "[shortcode] raw"},
        }
        row = content.project_post(record)
        assert row["content_is_raw"] is True
        assert row["content_html"] == "[shortcode] raw"

    def test_empty_content_becomes_none(self) -> None:
        row = content.project_post({**POST_RECORD, "content": {"rendered": "   "}})
        assert row["content_html"] is None


class TestTermAndUserProjection:
    def test_term_shape(self) -> None:
        row = content.project_term(
            {
                "id": 2678,
                "taxonomy": "category",
                "name": "Food &amp; Drink",
                "slug": "food-drink",
                "parent": 0,
                "count": 551,
                "description": "",
            }
        )
        assert row["term_id"] == 2678
        assert row["name"] == "Food & Drink"
        assert row["parent"] is None
        assert row["description"] is None

    def test_user_shape_leaves_unexposed_fields_none(self) -> None:
        row = content.project_user(
            {"id": 6146, "name": "GDA Gusde", "slug": "gda-gusde", "url": ""}
        )
        assert row["wp_id"] == 6146
        assert row["display_name"] == "GDA Gusde"
        assert row["login"] == "gda-gusde"
        assert row["email"] is None
        assert row["url"] is None

    def test_name_index_skips_rows_without_an_id(self) -> None:
        index = content.name_index(
            [
                {"term_id": 1, "name": "A"},
                {"term_id": None, "name": "B"},
                {"term_id": 3, "name": ""},
            ]
        )
        assert index == {1: "A"}
