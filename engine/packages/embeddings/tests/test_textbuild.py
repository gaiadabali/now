from now_embeddings.textbuild import (
    BODY_CHAR_BUDGET,
    build_article_text,
    build_place_text,
    build_term_text,
)


def test_article_text_includes_title_dek_body():
    text, digest = build_article_text(
        title="Rooftop Bars of Jakarta",
        dek="A guide to skyline drinking",
        body_blocks=[{"type": "paragraph", "html": "<p>Senopati has the best views.</p>"}],
        primary_type=None,
        format=None,
    )
    assert "Rooftop Bars of Jakarta" in text
    assert "A guide to skyline drinking" in text
    assert "Senopati has the best views." in text
    assert len(digest) == 64  # sha256 hex


def test_article_text_stable_hash_for_identical_input():
    args = dict(
        title="T", dek="D", body_blocks=[{"type": "paragraph", "html": "<p>Body.</p>"}],
        primary_type=None, format=None,
    )
    _, h1 = build_article_text(**args)
    _, h2 = build_article_text(**args)
    assert h1 == h2


def test_article_text_hash_changes_when_facets_added():
    """The whole point of hashing the *input text*, not the article id: once
    E2.1 fills primary_type/format, the same article's hash must change so
    the next backfill re-embeds it (task: "make re-embedding cheap")."""
    base = dict(title="T", dek="D", body_blocks=[{"type": "paragraph", "html": "<p>Body.</p>"}])
    _, h_before = build_article_text(**base, primary_type=None, format=None)
    _, h_after = build_article_text(**base, primary_type="eat", format="guide")
    assert h_before != h_after


def test_article_body_is_truncated_not_silently_passed_through():
    long_body = "word " * 2000  # far longer than BODY_CHAR_BUDGET
    text, _ = build_article_text(
        title="T", dek=None, body_blocks=[{"type": "paragraph", "html": f"<p>{long_body}</p>"}],
        primary_type=None, format=None,
    )
    # body contribution to the final text must not exceed the documented budget
    body_part = text.split("\n\n")[-1]
    assert len(body_part) <= BODY_CHAR_BUDGET


def test_article_text_empty_blocks_still_returns_title():
    text, digest = build_article_text(title="Only a title", dek=None, body_blocks=[], primary_type=None, format=None)
    assert text == "Only a title"
    assert len(digest) == 64


def test_place_text_includes_structured_fields():
    text, _ = build_place_text(
        name="Sky Lounge",
        address="Jl. Senopati No 1",
        area_term="senopati",
        place_type="drink",
        subtype="rooftop-bar",
        price_band="$$$",
        amenities=["rooftop", "pool"],
        cuisine=None,
        vibe=["romantic"],
    )
    assert "Sky Lounge" in text
    assert "rooftop-bar" in text
    assert "romantic" in text
    assert "senopati" in text


def test_term_text_includes_facet_context():
    text, digest = build_term_text(facet_key="cuisine", label="Japanese", slug="japanese")
    assert text == "cuisine: Japanese (japanese)"
    assert len(digest) == 64
