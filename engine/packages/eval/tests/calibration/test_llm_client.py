from now_eval.calibration.llm_client import build_prompt


def test_prompt_never_leaks_category_or_classifier_fields():
    messages = build_prompt(
        title="Sudestada Jakarta Opens",
        excerpt="A new Argentine restaurant in Menteng.",
        text_excerpt="Fans of Latin American cuisine rejoice...",
    )
    rendered = "\n".join(m["content"] for m in messages).lower()
    forbidden = ["wp category", "wordpress category", "classifier proposed",
                 "confidence", "primary_type", "primary category", "dining news"]
    for term in forbidden:
        assert term not in rendered, f"blind prompt leaked forbidden term: {term!r}"


def test_prompt_includes_the_article_text():
    messages = build_prompt("My Title", "My excerpt", "My body text")
    rendered = "\n".join(m["content"] for m in messages)
    assert "My Title" in rendered
    assert "My excerpt" in rendered
    assert "My body text" in rendered


def test_prompt_lists_every_vocabulary_slug():
    messages = build_prompt("t", "e", "b")
    system = messages[0]["content"]
    for slug in ("stay", "eat", "drink", "do", "wellness", "shop", "event", "editorial", "unknown"):
        assert slug in system
    for slug in ("news", "event", "offer", "review", "listing", "guide", "feature",
                 "heritage", "people", "city-guide", "opinion"):
        assert slug in system
