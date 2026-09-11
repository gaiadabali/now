"""
Independent, from-scratch re-implementation of the E1.2 content-loss metric.

Deliberately does NOT import anything from now_content_clean.metrics — uses
BeautifulSoup (a different HTML parser/library than their lxml-based one) and
an independently-written block-to-text walker, so this is not "running their
code on their code" (the exact blind spot the QA brief calls out).

Definition matched to their stated spec (README "Content-loss verification"):
  - visible text = tags/entities stripped, whitespace collapsed
  - alt text excluded from both sides
  - script/style/svg excluded from both sides
  - WP shortcode/comment markers stripped from the input side before compare
"""
import json
import re
import statistics
import sys
from bs4 import BeautifulSoup

ARTICLES = sys.argv[1]
BLOCKS = sys.argv[2]

WS_RE = re.compile(r"\s+")
WP_COMMENT_RE = re.compile(r"<!--\s*/?wp:.*?-->", re.DOTALL)
CAPTION_SHORTCODE_RE = re.compile(r"\[caption[^\]]*\]|\[/caption\]|\[gallery[^\]]*\]", re.IGNORECASE)


def normalize(text: str) -> str:
    return WS_RE.sub(" ", text or "").strip()


def visible_text_in(html: str) -> str:
    if not html or not html.strip():
        return ""
    cleaned = WP_COMMENT_RE.sub("", html)
    cleaned = CAPTION_SHORTCODE_RE.sub("", cleaned)
    soup = BeautifulSoup(cleaned, "html.parser")
    for tag in soup(["script", "style", "svg"]):
        tag.decompose()
    return normalize(soup.get_text(" "))


def strip_html_text(fragment: str) -> str:
    if not fragment:
        return ""
    soup = BeautifulSoup(fragment, "html.parser")
    for tag in soup(["script", "style", "svg"]):
        tag.decompose()
    return soup.get_text(" ")


def block_text(block: dict) -> str:
    t = block.get("type")
    if t in ("paragraph", "quote", "raw_html"):
        parts = [strip_html_text(block.get("html", ""))]
        if t == "quote" and block.get("cite"):
            parts.append(block["cite"])
        return " ".join(p for p in parts if p)
    if t == "heading":
        return block.get("text", "") or ""
    if t == "list":
        return " ".join(strip_html_text(i) for i in block.get("items", []))
    if t == "image":
        return block.get("caption") or ""
    if t == "gallery":
        parts = [img.get("caption") or "" for img in block.get("images", [])]
        if block.get("caption"):
            parts.append(block["caption"])
        return " ".join(p for p in parts if p)
    if t == "columns":
        return " ".join(block_text(b) for col in block.get("columns", []) for b in col)
    return ""


def visible_text_out(blocks: list) -> str:
    return normalize(" ".join(block_text(b) for b in blocks if block_text(b)))


# Load articles keyed by wp_id
articles_by_id = {}
with open(ARTICLES, encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if not line:
            continue
        row = json.loads(line)
        articles_by_id[row["wp_id"]] = row

results = []
with open(BLOCKS, encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if not line:
            continue
        rec = json.loads(line)
        wp_id = rec["wp_id"]
        article = articles_by_id.get(wp_id)
        if article is None:
            continue
        text_in = visible_text_in(article.get("content_html", ""))
        text_out = visible_text_out(rec.get("blocks", []))
        chars_in, chars_out = len(text_in), len(text_out)
        delta = chars_in - chars_out
        pct = (delta / chars_in * 100) if chars_in else 0.0
        results.append({"wp_id": wp_id, "chars_in": chars_in, "chars_out": chars_out,
                         "delta": delta, "loss_pct": round(pct, 3)})

pcts = [r["loss_pct"] for r in results]
print("n articles:", len(results))
print("median:", statistics.median(pcts))
print("p95:", sorted(pcts)[int(len(pcts) * 0.95)])
print("max:", max(pcts))

nonzero = [r for r in results if abs(r["loss_pct"]) > 0.0001]
print("nonzero-loss count:", len(nonzero))
for r in sorted(nonzero, key=lambda r: -abs(r["loss_pct"]))[:20]:
    print(r)

over10k = [r for r in results if r["chars_in"] > 10_000]
over10k_lossy = [r for r in over10k if abs(r["loss_pct"]) > 0.0001]
print("articles >10k chars:", len(over10k), "with any loss:", len(over10k_lossy))
for r in over10k_lossy[:20]:
    print("OVER10K LOSS:", r)

# write full results for evidence
with open(sys.argv[3], "w", encoding="utf-8") as out:
    json.dump({
        "n": len(results),
        "median": statistics.median(pcts),
        "p95": sorted(pcts)[int(len(pcts) * 0.95)],
        "max": max(pcts),
        "nonzero": nonzero,
        "over10k_with_loss": over10k_lossy,
    }, out, indent=2)
