"""WS6 step 1: is this corpus multilingual enough for a multilingual
embedding model to matter?

Measures, for every published article in every registered site (read
from `now_platform.engine.sites`, so no city is named here -- the same
registry-driven iteration the worker uses):

1. **Language mix of the exact text that gets embedded** -- the string
   `store.fetch_articles` builds (title + dek + body[:BODY_CHAR_BUDGET]),
   not the raw article, because that string is the only thing the model
   ever sees. Also measured over the *full* body, so a reader can tell
   whether Indonesian lives past the truncation point.
2. **Median token length** of that text under each candidate model's own
   tokenizer, untruncated -- so "does the 512-token window bind?" is
   answered per tokenizer (WordPiece and XLM-R SentencePiece split
   Indonesian very differently).
3. **Language of the search ground truth** (Yoast focus keywords from
   the extracted archive), since a multilingual model can only help
   search if queries are actually Indonesian.

Method, and its limits (also written up in docs/EDITION-2-PLAN.md WS6):

* Text is split into segments on blank lines and sentence punctuation;
  every segment with >= MIN_SEGMENT_LETTERS letters is classified by
  `langdetect` (Nakatani's n-gram profiles, seeded for determinism).
  Per-article Indonesian share = Indonesian-classified letters / all
  classified letters. Buckets: English (< MIXED_AT), mixed (MIXED_AT up
  to INDONESIAN_AT), Indonesian (>= INDONESIAN_AT).
* langdetect is unreliable below ~20 characters and confuses Indonesian
  with Malay/Tagalog/Somali on short, name-heavy strings, so a second,
  independent signal is computed per segment: the rate of the 30 most
  frequent Indonesian function words (yang, dan, di, ...), which English
  prose essentially never contains. A segment counts as Indonesian under
  the lexical test when >= LEXICAL_ID_RATE of its tokens are those words.
  Both numbers are reported; agreement between them is the confidence.
* Proper nouns and loanwords inside English prose (warung, nasi goreng,
  Jalan, banjar) are NOT Indonesian text by either test -- a sentence of
  English that names a warung is English. They are counted separately
  (`loanword_docs`) because that is the one place an English-only model
  could plausibly be weak even on an English corpus.

Run (from engine/packages/embeddings, with NOW_PG_* set as for backfill):
    uv run --extra model-eval python scripts/measure_corpus_language.py \
        --out <path/to/report.json>
"""

from __future__ import annotations

import argparse
import json
import re
import statistics
from collections import Counter
from pathlib import Path

from sqlalchemy import text

from now_db.sites_registry import list_sites
from now_embeddings.connections import city_engine, platform_engine
from now_embeddings.store import fetch_articles

MIN_SEGMENT_LETTERS = 20
MIXED_AT = 0.10
INDONESIAN_AT = 0.50
LEXICAL_ID_RATE = 0.12

# Top Indonesian function words (closed-class: none are English words or
# common proper-noun fragments in this archive). Deliberately excludes
# "ini"/"itu" look-alikes and anything that is also an English token.
ID_FUNCTION_WORDS = frozenset(
    "yang dan di untuk dengan dari dalam tidak akan pada juga adalah ke ini itu "
    "kami kita atau sudah bisa ada lebih oleh karena saat telah sebagai hingga "
    "serta namun para".split()
)
LOANWORDS = frozenset(
    "warung nasi goreng babi guling sate satay sambal jalan jl. gang pura banjar "
    "kopi mie bakso rendang gado-gado ojek becak pasar kampung desa kuta canggu "
    "ubud seminyak batik wayang gamelan galungan nyepi kecak".split()
)

_SEG_SPLIT = re.compile(r"(?:\n\s*\n|(?<=[.!?])\s+)")
_WORD = re.compile(r"[a-zA-ZÀ-ɏ'-]+")


def _segments(txt: str) -> list[str]:
    return [s.strip() for s in _SEG_SPLIT.split(txt) if s and s.strip()]


def _letters(s: str) -> int:
    return sum(1 for ch in s if ch.isalpha())


def _lexical_is_indonesian(seg: str) -> bool:
    words = [w.lower() for w in _WORD.findall(seg)]
    if len(words) < 4:
        return False
    return sum(1 for w in words if w in ID_FUNCTION_WORDS) / len(words) >= LEXICAL_ID_RATE


def _detector():
    from langdetect import DetectorFactory, detect

    DetectorFactory.seed = 0

    def _detect(seg: str) -> str:
        try:
            return detect(seg)
        except Exception:  # noqa: BLE001 -- langdetect raises on featureless input
            return "unk"

    return _detect


def language_profile(txt: str, detect) -> dict:
    """Per-text shares by both instruments. Pure function of `txt` -- the
    unit test pins its behaviour on hand-written English/Indonesian text."""
    counted = 0
    by_lang: Counter[str] = Counter()
    lexical_id = 0
    for seg in _segments(txt):
        n = _letters(seg)
        if n < MIN_SEGMENT_LETTERS:
            continue
        counted += n
        by_lang[detect(seg)] += n
        if _lexical_is_indonesian(seg):
            lexical_id += n
    if counted == 0:
        return {"letters": 0, "id_share_langdetect": 0.0, "id_share_lexical": 0.0, "by_lang": {}}
    return {
        "letters": counted,
        "id_share_langdetect": by_lang.get("id", 0) / counted,
        "id_share_lexical": lexical_id / counted,
        "by_lang": dict(by_lang),
    }


def bucket(share: float) -> str:
    if share >= INDONESIAN_AT:
        return "indonesian"
    if share >= MIXED_AT:
        return "mixed"
    return "english"


def _full_body_text(conn, article_id: str) -> str:
    from now_content_clean.metrics import visible_text_out

    row = conn.execute(text("SELECT title, dek, body_blocks FROM public.articles WHERE id=:id"), {"id": int(article_id)}).first()
    return "\n\n".join(p for p in (row[0], row[1], visible_text_out(row[2] or [])) if p)


def _tokenizers(names: list[str]):
    from tokenizers import Tokenizer

    out = {}
    for name in names:
        tok = Tokenizer.from_pretrained(name)
        tok.no_truncation()
        tok.no_padding()
        out[name] = tok
    return out


def _focus_keywords(articles_jsonl: Path) -> list[str]:
    out = []
    with open(articles_jsonl, encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            meta = json.loads(line).get("meta") or {}
            kw = meta.get("_yoast_wpseo_focuskw")
            if isinstance(kw, str) and kw.strip():
                out.append(kw.strip())
    return out


def _query_is_indonesian(q: str) -> bool:
    words = [w.lower() for w in _WORD.findall(q)]
    return any(w in ID_FUNCTION_WORDS for w in words)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument(
        "--tokenizer",
        action="append",
        default=None,
        help="HF tokenizer id, repeatable (default: current model + the multilingual candidates' tokenizers).",
    )
    ap.add_argument(
        "--focus-keywords",
        action="append",
        default=[],
        help="site_slug=path/to/articles.jsonl, repeatable -- the extracted archive the search ground truth is built from.",
    )
    args = ap.parse_args()
    tokenizer_names = args.tokenizer or ["BAAI/bge-small-en-v1.5", "intfloat/multilingual-e5-small", "BAAI/bge-m3"]
    toks = _tokenizers(tokenizer_names)
    detect = _detector()

    with platform_engine().connect() as pconn:
        sites = [s for s in list_sites(pconn) if s.db_ref]

    report: dict = {"method": {
        "min_segment_letters": MIN_SEGMENT_LETTERS, "mixed_at": MIXED_AT,
        "indonesian_at": INDONESIAN_AT, "lexical_id_rate": LEXICAL_ID_RATE,
    }, "sites": {}}
    for site in sites:
        engine = city_engine(site.db_ref)
        try:
            with engine.connect() as conn:
                rows = fetch_articles(conn)
        except Exception as exc:  # noqa: BLE001 -- a site with no Payload schema (the synthetic tenant) is skipped, not fatal
            print(f"[{site.slug}] skipped: {type(exc).__name__}")
            continue
        if not rows:
            print(f"[{site.slug}] no published articles, skipped")
            continue
        buckets_ld: Counter[str] = Counter()
        buckets_lex: Counter[str] = Counter()
        buckets_full: Counter[str] = Counter()
        agree = 0
        loanword_docs = 0
        tok_lens: dict[str, list[int]] = {n: [] for n in toks}
        char_lens = []
        other_langs: Counter[str] = Counter()
        examples: dict[str, list[str]] = {"mixed": [], "indonesian": []}
        with engine.connect() as conn:
            for r in rows:
                prof = language_profile(r.text, detect)
                b_ld = bucket(prof["id_share_langdetect"])
                b_lex = bucket(prof["id_share_lexical"])
                buckets_ld[b_ld] += 1
                buckets_lex[b_lex] += 1
                agree += b_ld == b_lex
                for lang, n in prof["by_lang"].items():
                    other_langs[lang] += n
                if b_ld != "english" and len(examples[b_ld]) < 5:
                    examples[b_ld].append(f"{r.entity_id}: {r.text[:90]!r}")
                words = {w.lower() for w in _WORD.findall(r.text)}
                loanword_docs += bool(words & LOANWORDS)
                char_lens.append(len(r.text))
                for name, tok in toks.items():
                    tok_lens[name].append(len(tok.encode(r.text).ids))
                full = language_profile(_full_body_text(conn, r.entity_id), detect)
                buckets_full[bucket(full["id_share_langdetect"])] += 1

        n = len(rows)
        site_report = {
            "articles": n,
            "embedded_text_buckets_langdetect": {k: [buckets_ld[k], round(100 * buckets_ld[k] / n, 2)] for k in ("english", "mixed", "indonesian")},
            "embedded_text_buckets_lexical": {k: [buckets_lex[k], round(100 * buckets_lex[k] / n, 2)] for k in ("english", "mixed", "indonesian")},
            "full_body_buckets_langdetect": {k: [buckets_full[k], round(100 * buckets_full[k] / n, 2)] for k in ("english", "mixed", "indonesian")},
            "instrument_agreement_pct": round(100 * agree / n, 2),
            "letters_by_detected_lang_top": other_langs.most_common(8),
            "docs_with_indonesian_loanwords_pct": round(100 * loanword_docs / n, 2),
            "embedded_text_chars_median": statistics.median(char_lens),
            "tokens_untruncated": {
                name: {
                    "median": statistics.median(v),
                    "p90": sorted(v)[int(0.9 * (len(v) - 1))],
                    "max": max(v),
                    "pct_over_512": round(100 * sum(1 for x in v if x > 512) / len(v), 2),
                }
                for name, v in tok_lens.items()
            },
            "examples": examples,
        }
        report["sites"][site.slug] = site_report
        print(json.dumps({site.slug: site_report}, indent=2, ensure_ascii=False))

    fk_report = {}
    for spec in args.focus_keywords:
        slug, path = spec.split("=", 1)
        kws = _focus_keywords(Path(path))
        id_kws = [k for k in kws if _query_is_indonesian(k)]
        loan_kws = [k for k in kws if {w.lower() for w in _WORD.findall(k)} & LOANWORDS]
        fk_report[slug] = {
            "focus_keywords": len(kws),
            "with_indonesian_function_word": len(id_kws),
            "pct": round(100 * len(id_kws) / len(kws), 2) if kws else 0.0,
            "with_indonesian_loanword": len(loan_kws),
            "loanword_pct": round(100 * len(loan_kws) / len(kws), 2) if kws else 0.0,
            "examples": id_kws[:15],
            "loanword_examples": loan_kws[:10],
        }
    report["focus_keywords"] = fk_report
    print(json.dumps({"focus_keywords": fk_report}, indent=2, ensure_ascii=False))
    args.out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
