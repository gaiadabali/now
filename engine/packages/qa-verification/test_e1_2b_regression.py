"""QA.2 regression tests for E1.2b (<br> word-merge + content-loss symmetry).

These do NOT exist anywhere in engine/packages/content-clean/tests/ — verified
by grep (zero hits for "apply_render_boundaries", "<br", or "word-merge" in
that tests/ dir). That means the exact bug class QA.1 found (and E1.2b fixed)
has no regression coverage: a future change could reintroduce the <br>
word-merge and the existing 44-test suite would stay green.

Run with the content-clean package's own venv:
    cd engine/packages/content-clean
    .venv/Scripts/python -m pytest ../qa-verification/test_e1_2b_regression.py -v
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "content-clean" / "src"))

from now_content_clean.html_blocks import strip_tags_text  # noqa: E402
from now_content_clean.metrics import content_loss, visible_text_in, visible_text_out  # noqa: E402
from now_content_clean.html_blocks import blocks_from_fragment  # noqa: E402


def test_br_inserts_word_boundary():
    """The original bug: strip_tags_text used to weld words across <br>."""
    html = "the<br>colonial period"
    assert strip_tags_text(html) == "the colonial period"


def test_br_already_spaced_is_byte_identical_to_pre_fix_output():
    """Guard against the fix over-correcting: for an already-spaced <br>,
    apply_render_boundaries' guard (`not tail[:1].isspace()`) must skip
    insertion, so the fixed strip_tags_text() output is byte-identical to
    the PRE-FIX raw lxml text_content() output -- including a pre-existing
    double space that is an artifact of naive concatenation (parent text
    ending in a space + void <br> + tail starting with a space), NOT
    something the fix adds. This is the "252 already-correctly-spaced
    occurrences must not gain a redundant second space" claim, verified
    precisely: the fix adds zero characters here, whatever lxml already
    produced (single or double space) is preserved unchanged."""
    import lxml.html as _lxml_html

    html = "the <br> colonial period"
    pre_fix = _lxml_html.fragment_fromstring(html, create_parent="div").text_content()
    post_fix = strip_tags_text(html)
    assert post_fix == pre_fix, f"fix changed output: pre={pre_fix!r} post={post_fix!r}"


def test_metric_is_symmetric_on_br_case():
    """Both sides of the loss metric must flatten a <br> the same way, or
    the metric reports a phantom delta on content that suffered zero real
    loss."""
    html = "<p>the<br>colonial period</p>"
    stats = {}
    blocks = blocks_from_fragment(html, stats)
    result = content_loss(html, blocks)
    assert result["loss_pct"] == 0.0, result


def test_known_source_weld_nastarand_is_reproduced_not_fixed():
    """Real corpus case (article slug
    'premium-heritage-bread-cakes-and-finger-food-from-holland-bakery'):
    '<em>nastar</em>and' welds to 'nastarand' because inline tags are
    deliberately excluded from boundary insertion. This documents that the
    inline-tag exclusion is a real, live source of welded words in the
    shipped corpus -- it is a *pre-existing source-content* defect (no
    space in the raw HTML either, so a browser renders it the same way),
    not a new regression introduced by E1.2b, but it proves the inline
    exclusion is not cost-free in this corpus.
    """
    html = "the best <em>nastar</em>and <em>lapis legit </em>always use Dutch Wijsman butter."
    out = strip_tags_text(html)
    assert "nastarand" in out  # documents current (unchanged) behavior


def test_double_br_collapses_two_paragraphs_into_one_run_with_zero_reported_loss():
    """Adversarial case for metric-symmetry masking: a human reading
    '<p>First paragraph ends here.<br><br>Second paragraph starts
    here.</p>' sees two visually distinct paragraphs (blank line from the
    double <br>). The block extractor turns this into a single paragraph
    block, and the char-based metric -- symmetric on both sides -- reports
    0% loss because no characters/words are missing, only the paragraph
    boundary. This is not a NEW regression from E1.2b (the metric was
    never designed to measure structure) but it is a real masking risk
    worth flagging per the QA.2 ticket.
    """
    html = "<p>First paragraph ends here.<br><br>Second paragraph starts here.</p>"
    stats = {}
    blocks = blocks_from_fragment(html, stats)
    result = content_loss(html, blocks)
    assert result["loss_pct"] == 0.0
    assert len(blocks) == 1  # two visual paragraphs collapsed into one block
    assert blocks[0]["type"] == "paragraph"


if __name__ == "__main__":
    import traceback
    tests = [v for k, v in list(globals().items()) if k.startswith("test_")]
    failed = 0
    for t in tests:
        try:
            t()
            print(f"PASS {t.__name__}")
        except AssertionError:
            failed += 1
            print(f"FAIL {t.__name__}")
            traceback.print_exc()
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
