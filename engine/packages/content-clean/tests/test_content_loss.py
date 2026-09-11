"""Acceptance-criteria tests: content-loss measurement over the real
fixture sample (133 real articles pulled from the raw WordPress dump —
see tests/fixtures/README or the package README's "Fixture provenance"
section)."""

from __future__ import annotations

import statistics

from now_content_clean.pipeline import clean_article


def test_133_fixture_articles_all_run_without_crashing(articles):
    assert len(articles) >= 100, "fixture sample must have 100+ real articles per the ticket"
    for article in articles:
        result = clean_article(article)
        assert isinstance(result.blocks, list)


def test_zero_content_loss_over_10k_chars(articles):
    """Hard acceptance criterion: articles > 10k chars must show zero
    visible-text loss — this is exactly where naive parsers silently
    truncate."""
    checked = 0
    for article in articles:
        loss = clean_article(article).stats["content_loss"]
        if loss["chars_in"] > 10_000:
            checked += 1
            assert loss["chars_out"] == loss["chars_in"], (
                f"wp_id={article['wp_id']} lost {loss['delta']} chars "
                f"({loss['loss_pct']}%) on a {loss['chars_in']}-char article"
            )
    assert checked > 0, "fixture sample must include at least one article > 10k chars"


def test_content_loss_across_sample_is_negligible(articles):
    """Soft, aggregate check: loss across the whole sample is ~0 — the
    small residual (< 2%) that does occur is entirely bare oEmbed URLs
    (a `wp:embed`'s raw URL text, replaced by a player, intentionally not
    counted as rendered prose — see the package README)."""
    pcts = [abs(clean_article(a).stats["content_loss"]["loss_pct"]) for a in articles]
    assert statistics.median(pcts) == 0.0
    assert max(pcts) < 2.0, f"unexpected content loss outlier: {max(pcts)}%"


def test_tracking_script_never_leaks_into_a_block(articles_by_id):
    """wp_id 6640 ends with an inline Tealium tracking `<script>` — it
    must never appear in the output, and dropping it must not register
    as content loss (it has zero rendered text either way)."""
    article = articles_by_id[6640]
    result = clean_article(article)
    assert "utag_data" not in str(result.blocks), "tracking JS must never leak into a block"
    loss = result.stats["content_loss"]
    assert loss["chars_out"] == loss["chars_in"]
    assert result.stats.get("dropped_non_visible", 0) >= 1


def test_max_length_article_does_not_blow_up(articles):
    """The 153k-char maximum must be handled — completes, produces
    blocks, loses nothing."""
    longest = max(articles, key=lambda a: len(a["content_html"]))
    assert len(longest["content_html"]) > 100_000
    result = clean_article(longest)
    assert len(result.blocks) > 0
    loss = result.stats["content_loss"]
    assert loss["chars_out"] == loss["chars_in"]


def test_pipeline_is_idempotent(articles):
    """Re-running the pure function on the same input must yield
    byte-identical output (the ingest job must be safely re-runnable)."""
    for article in articles[:20]:
        r1 = clean_article(article)
        r2 = clean_article(article)
        assert r1.blocks == r2.blocks
        assert r1.stats == r2.stats
        assert [l.__dict__ for l in r1.links] == [l.__dict__ for l in r2.links]
