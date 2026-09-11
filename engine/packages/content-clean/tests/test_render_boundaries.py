"""Regression tests for the `<br>` word-weld defect (E1.2b) and the
boundary-insertion rules around it.

Found by QA.1: a bare `<br>` inside a `<figcaption>` was welding the words
either side ("during the<br>colonial" -> "during thecolonial"). Character
count is unchanged by a weld, so the content-loss metric could not see it.

Found by QA.2 auditing the fix: inserting a boundary on BOTH a `<br>` and its
enclosing whitespace-rendering parent produced a double space when the `<br>`
was the parent's last child.

These live in the package (not in a throwaway QA script) so the defect class
stays covered.
"""
from __future__ import annotations

from now_content_clean.html_blocks import strip_tags_text
from now_content_clean.metrics import word_delta


def test_bare_br_does_not_weld_words():
    html = "<figcaption>during the<br>colonial period.</figcaption>"
    assert "thecolonial" not in strip_tags_text(html)
    assert "the colonial" in strip_tags_text(html)


def test_br_as_last_child_does_not_double_space():
    """QA.2 found 10 real articles shaped like this. Both the <br> and the
    enclosing <figcaption> wanted to insert at the same textual position."""
    html = "<figure><figcaption>Courtesy of Yavuz Gallery.<br></figcaption></figure>"
    assert "  " not in strip_tags_text(html)


def test_nested_last_child_chain_does_not_double_space():
    html = "<div><p>Ends here.<br></p></div>"
    assert "  " not in strip_tags_text(html)


def test_existing_whitespace_is_not_added_to():
    """The source already has a space on BOTH sides of the <br>, so flattening
    legitimately yields two — that whitespace is in the source, not inserted by
    us, and matches pre-fix behaviour byte for byte. What must not happen is a
    third space being added on top."""
    html = "<figcaption>word <br> word</figcaption>"
    assert strip_tags_text(html) == "word  word"


def test_pure_inline_tags_do_not_gain_a_boundary():
    """`<b>bold</b>text` genuinely renders as "boldtext" — inserting a space
    would corrupt the text rather than repair it."""
    assert strip_tags_text("<p><b>bold</b>text</p>") == "boldtext"
    assert strip_tags_text("<p><em>nastar</em>and</p>") == "nastarand"


def test_block_elements_separate_words():
    assert strip_tags_text("<div><p>alpha</p><p>beta</p></div>") == "alpha beta"


def test_word_delta_detects_a_weld_that_char_count_misses():
    """The whole point: a weld is invisible to a character count."""
    welded = "during thecolonial period"
    correct = "during the colonial period"
    # Character counts differ by exactly the one missing space...
    assert len(correct) - len(welded) == 1
    d = word_delta(correct, welded)
    assert d["words_lost"] == 2  # "the", "colonial"
    assert d["words_gained"] == 1  # "thecolonial"


def test_word_delta_clean_when_text_matches():
    d = word_delta("alpha beta gamma", "alpha beta gamma")
    assert d["words_lost"] == 0 and d["words_gained"] == 0
