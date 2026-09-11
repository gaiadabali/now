from now_eval.calibration.subtype import SUBTYPE_VOCABULARY, build_prompt, label_sample


def test_vocabulary_has_66_terms():
    # F115: 66 subtype terms exist in now_platform.engine.terms -- if this
    # drifts, the hardcoded prompt vocabulary needs a resync (see module
    # docstring for why it's hardcoded rather than read live).
    assert len(SUBTYPE_VOCABULARY) == 66


def test_prompt_stays_blind():
    messages = build_prompt(
        title="Sudestada Jakarta Opens",
        excerpt="A new Argentine restaurant in Menteng.",
        text_excerpt="Fans of Latin American cuisine rejoice...",
    )
    rendered = "\n".join(m["content"] for m in messages).lower()
    forbidden = [
        "wp category", "wordpress category", "classifier proposed", "confidence",
        "primary_type", "primary category", "resolved type", "category-fixed",
        "keyword match",
    ]
    for term in forbidden:
        assert term not in rendered, f"blind subtype prompt leaked forbidden term: {term!r}"


def test_prompt_includes_the_article_text_and_full_vocabulary():
    messages = build_prompt("My Title", "My excerpt", "My body text")
    rendered = "\n".join(m["content"] for m in messages)
    assert "My Title" in rendered
    assert "My excerpt" in rendered
    assert "My body text" in rendered
    for slug in ("restaurant", "hotel", "zoo", "wine-bar", "place-of-worship"):
        assert slug in rendered


def test_prompt_offers_the_literal_unresolved_fallback():
    # Must match now_classifier's own literal no-match value exactly, so
    # `adjudication.merge`'s `llm_value == proposed_value` comparison works
    # without any normalisation step -- see module docstring.
    messages = build_prompt("t", "e", "b")
    system = messages[0]["content"]
    assert '"unresolved"' in system


def test_label_sample_is_resumable(tmp_path, monkeypatch):
    sample_path = tmp_path / "subtype_sample.jsonl"
    out_path = tmp_path / "subtype_llm_labels.jsonl"
    sample_path.write_text(
        '{"key": "jakarta:1:subtype", "city": "jakarta", "wp_id": 1, "facet": "subtype", '
        '"proposed_value": "restaurant", "confidence": 0.7, "source": "ai", "outcome": "review", '
        '"title": "t", "excerpt": "e", "text_excerpt": "b", "categories": []}\n',
        encoding="utf-8",
    )
    # Pre-seed out_path as if wp_id 1 was already labelled -- label_sample
    # must not call the network for it again.
    out_path.write_text(
        '{"city": "jakarta", "wp_id": 1, "subtype": "restaurant", "reasoning": "r", '
        '"format_reasoning": "r", "raw": "", "error": null}\n',
        encoding="utf-8",
    )

    called = []

    def fake_classify(*args, **kwargs):
        called.append(args)
        raise AssertionError("should not be called -- wp_id 1 is already labelled")

    monkeypatch.setattr("now_eval.calibration.subtype.classify_subtype", fake_classify)
    monkeypatch.setattr(
        "now_eval.calibration.llm_client.load_ollama_env",
        lambda: {"OLLAMA_CLOUD_BASE_URL": "http://x", "OLLAMA_CLOUD_API_KEY": "k"},
    )

    stats = label_sample(sample_path, out_path, sleep_between=0)
    assert stats["already_done"] == 1
    assert stats["processed_this_run"] == 0
    assert called == []
