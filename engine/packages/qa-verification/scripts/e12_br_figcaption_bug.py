"""
Standalone regression repro for the E1.2 content-clean defect found during
QA verification of Wave 1-3 (waves-1-3-independent-verification task).

Defect: a bare `<br>` (no adjacent whitespace) inside a `<figcaption>` is
removed without inserting a word-boundary, so the two words on either side
of the line break are concatenated in the output block's `caption` field
(e.g. "...during the<br>colonial period." -> "...during thecolonial
period."). This corrupts rendered text; it is invisible to the package's
own char-count content-loss metric because no characters are actually
dropped (nothing shrinks the char count enough to register), which is
exactly the kind of defect a self-referential metric can't catch.

Run against a checkout that has now-content-clean importable:
    PYTHONPATH=<repo>/engine/packages/content-clean/src python3 \
        engine/packages/qa-verification/scripts/e12_br_figcaption_bug.py

Expected (current, buggy) output: FAIL lines showing merged words.
"""
from __future__ import annotations

from now_content_clean.pipeline import clean_article

CASES = [
    {
        "wp_id": 98687,
        "content_html": (
            '<!-- wp:image {"id":1} -->\n'
            '<figure class="wp-block-image"><img src="https://example.com/a.jpg" alt=""/>'
            "<figcaption><em>Exteriors of the buildings that were used to store spices "
            "collected from all over Indonesia during the<br>colonial period.</em></figcaption>"
            "</figure>\n<!-- /wp:image -->"
        ),
        "must_contain": "during the colonial period",
        "must_not_contain": "thecolonial",
    },
    {
        "wp_id": 94570,
        "content_html": (
            '<!-- wp:gallery {"linkTo":"none"} -->\n'
            '<figure class="wp-block-gallery"><!-- wp:image {"id":2} -->\n'
            '<figure class="wp-block-image"><img src="https://example.com/b.jpg" alt=""/>'
            "<figcaption>Museum MACAN, Jakarta<br>Courtesy of the artist and Audemars Piguet"
            "</figcaption></figure>\n<!-- /wp:image --></figure>\n<!-- /wp:gallery -->"
        ),
        "must_contain": "Jakarta Courtesy",
        "must_not_contain": "JakartaCourtesy",
    },
]


def caption_text(blocks: list[dict]) -> str:
    parts = []
    for b in blocks:
        if b.get("type") == "image" and b.get("caption"):
            parts.append(b["caption"])
        if b.get("type") == "gallery":
            for img in b.get("images", []):
                if img.get("caption"):
                    parts.append(img["caption"])
    return " ".join(parts)


def main() -> int:
    failures = 0
    for case in CASES:
        result = clean_article({"wp_id": case["wp_id"], "content_html": case["content_html"]})
        text = caption_text(result.blocks)
        ok = case["must_contain"] in text and case["must_not_contain"] not in text
        status = "PASS" if ok else "FAIL"
        if not ok:
            failures += 1
        print(f"[{status}] wp_id={case['wp_id']} caption={text!r}")
    print(f"\n{len(CASES) - failures}/{len(CASES)} passed")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
