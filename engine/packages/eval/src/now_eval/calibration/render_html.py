"""Step 4: render the adjudication queue as one self-contained, offline HTML
file Hansel opens locally (`file://...`) -- no server, no Artifact hosting
(this carries unpublished editorial content + live DB state, so it stays
local). Keyboard-driven on purpose: task brief says "keyboard-friendly
choice," and this is a one-sitting task, not a dashboard.

Verdict schema (written back out as JSON, one object per adjudicated item):
`{item_id: "classifier" | "llm" | "neither"}`. For a `"control"` item (the
classifier and LLM already agreed) "classifier"/"llm" are the same outcome
by construction -- the UI just labels the two buttons "Correct" / "Wrong" --
but the same verdict vocabulary keeps `analyze.py` able to treat both kinds
identically (it only asks "was the classifier's value ruled correct?").
Progress persists in the browser's own localStorage keyed by queue file
hash, so closing the tab mid-session loses nothing; "Export verdicts"
downloads the JSON `apply_adjudication.py` (or `analyze.py` directly) reads.
"""
from __future__ import annotations

import html as html_mod
import json
from pathlib import Path


def render(items: list[dict], *, title: str = "F96 confidence calibration -- adjudication") -> str:
    payload = json.dumps(items, ensure_ascii=False)
    n = len(items)
    n_disagree = sum(1 for i in items if i["kind"] == "disagreement")
    n_control = n - n_disagree
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{html_mod.escape(title)}</title>
<style>
  :root {{ color-scheme: light dark; }}
  body {{ font-family: -apple-system, Segoe UI, Roboto, sans-serif; max-width: 820px; margin: 0 auto; padding: 24px 20px 80px;
          background: Canvas; color: CanvasText; }}
  h1 {{ font-size: 1.1rem; margin-bottom: 4px; }}
  .sub {{ color: GrayText; font-size: 0.85rem; margin-bottom: 20px; }}
  .progress {{ position: sticky; top: 0; background: Canvas; padding: 10px 0; border-bottom: 1px solid color-mix(in srgb, CanvasText 20%, transparent); margin-bottom: 16px; }}
  .bar {{ height: 6px; background: color-mix(in srgb, CanvasText 12%, transparent); border-radius: 3px; overflow: hidden; margin-top: 6px; }}
  .bar > div {{ height: 100%; background: #3b82f6; width: 0%; transition: width .2s; }}
  .card {{ border: 1px solid color-mix(in srgb, CanvasText 20%, transparent); border-radius: 10px; padding: 18px; margin-bottom: 14px; }}
  .meta {{ font-size: 0.75rem; color: GrayText; margin-bottom: 10px; display: flex; gap: 10px; flex-wrap: wrap; }}
  .meta span {{ background: color-mix(in srgb, CanvasText 8%, transparent); padding: 2px 8px; border-radius: 999px; }}
  .title {{ font-size: 1.05rem; font-weight: 600; margin: 0 0 6px; }}
  .excerpt {{ font-size: 0.9rem; color: color-mix(in srgb, CanvasText 75%, transparent); margin-bottom: 4px; }}
  .body {{ font-size: 0.85rem; color: color-mix(in srgb, CanvasText 65%, transparent); max-height: 6.5em; overflow: hidden; margin-bottom: 12px; }}
  .proposals {{ display: flex; gap: 10px; margin-bottom: 12px; flex-wrap: wrap; }}
  .proposal {{ flex: 1; min-width: 200px; border: 1px solid color-mix(in srgb, CanvasText 15%, transparent); border-radius: 8px; padding: 10px; }}
  .proposal b {{ display: block; font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.04em; color: GrayText; margin-bottom: 4px; }}
  .proposal .value {{ font-size: 1.05rem; font-weight: 700; }}
  .proposal .why {{ font-size: 0.8rem; color: GrayText; margin-top: 4px; }}
  .choices {{ display: flex; gap: 8px; flex-wrap: wrap; }}
  button {{ font: inherit; padding: 8px 14px; border-radius: 8px; border: 1px solid color-mix(in srgb, CanvasText 25%, transparent);
            background: Canvas; color: CanvasText; cursor: pointer; }}
  button:hover {{ background: color-mix(in srgb, CanvasText 8%, transparent); }}
  button.kbd::after {{ content: attr(data-key); font-size: 0.7rem; margin-left: 6px; opacity: .6; border: 1px solid currentColor; border-radius: 4px; padding: 0 4px; }}
  .done .card {{ opacity: 0.45; }}
  .verdict-badge {{ font-size: 0.75rem; font-weight: 600; padding: 2px 8px; border-radius: 999px; }}
  .verdict-classifier {{ background: #dcfce7; color: #166534; }}
  .verdict-llm {{ background: #dbeafe; color: #1e40af; }}
  .verdict-neither {{ background: #fee2e2; color: #991b1b; }}
  .toolbar {{ position: fixed; bottom: 0; left: 0; right: 0; background: Canvas; border-top: 1px solid color-mix(in srgb, CanvasText 20%, transparent);
              padding: 10px 20px; display: flex; gap: 10px; justify-content: center; }}
  #empty {{ text-align: center; padding: 60px 0; color: GrayText; }}
</style>
</head>
<body>
<h1>{html_mod.escape(title)}</h1>
<p class="sub">{n} items to adjudicate ({n_disagree} classifier/LLM disagreements, {n_control} random control agreements).
For a disagreement: which one is actually right, reading the article yourself? For a control item, the classifier and the
blind LLM already agreed -- just confirm whether that shared value is actually correct. Keyboard: <b>1</b>/<b>2</b>/<b>3</b>
pick a choice, <b>&larr;</b> back.</p>
<div class="progress">
  <span id="progress-text">0 / {n} done</span>
  <div class="bar"><div id="progress-fill"></div></div>
</div>
<div id="stage"></div>
<div id="empty" hidden>All done. Click "Export verdicts" below.</div>
<div class="toolbar">
  <button id="export">Export verdicts (.json)</button>
  <button id="reset">Reset progress</button>
</div>
<script>
const ITEMS = {payload};
const STORE_KEY = "now-eval-calibration-verdicts-v1";

function loadVerdicts() {{
  try {{ return JSON.parse(localStorage.getItem(STORE_KEY) || "{{}}"); }} catch (e) {{ return {{}}; }}
}}
function saveVerdicts(v) {{
  try {{ localStorage.setItem(STORE_KEY, JSON.stringify(v)); }} catch (e) {{ /* private mode etc -- degrade silently, export still works this session */ }}
}}

let verdicts = loadVerdicts();
let cursor = 0;

function pendingIndices() {{
  return ITEMS.map((it, i) => i).filter(i => !(ITEMS[i].item_id in verdicts));
}}

function render() {{
  const pending = pendingIndices();
  document.getElementById("progress-text").textContent = `${{ITEMS.length - pending.length}} / ${{ITEMS.length}} done`;
  document.getElementById("progress-fill").style.width = `${{100 * (ITEMS.length - pending.length) / ITEMS.length}}%`;
  const stage = document.getElementById("stage");
  const empty = document.getElementById("empty");
  if (pending.length === 0) {{
    stage.innerHTML = "";
    empty.hidden = false;
    return;
  }}
  empty.hidden = true;
  const idx = pending[0];
  const it = ITEMS[idx];
  const isControl = it.kind === "control";
  // `location` is multi-valued and this item is a yes/no validation of ONE
  // proposed value (not a forced single-choice between two proposals, which
  // would systematically mishandle "both are true at once" -- see
  // location.py's module docstring) -- always render the 2-button
  // confirm/reject UI for it, regardless of whether the LLM's own verdict
  // agreed (kind="control") or flagged it (kind="disagreement").
  const isValidation = it.facet === "location";
  stage.innerHTML = `
    <div class="card">
      <div class="meta">
        <span>${{it.city}}</span><span>${{it.facet}}</span>
        ${{it.provenance ? `<span>${{it.provenance}}</span>` : `<span>confidence ${{it.confidence}}</span>`}}
        <span>${{it.outcome === 'accepted' ? 'auto-applied' : 'sent to review'}}</span>
        <span>${{isControl ? (isValidation ? 'LLM confirmed (control)' : 'control (agreement)') : (isValidation ? 'LLM flagged as wrong' : 'disagreement')}}</span>
      </div>
      <p class="title">${{escapeHtml(it.title)}}</p>
      ${{it.excerpt ? `<p class="excerpt">${{escapeHtml(it.excerpt)}}</p>` : ""}}
      <p class="body">${{escapeHtml(it.text_excerpt)}}</p>
      <div class="proposals">
        <div class="proposal">
          <b>${{isValidation ? 'Proposed location' : 'Classifier proposes'}}</b>
          <div class="value">${{escapeHtml(it.classifier_value ?? "(none)")}}</div>
          ${{isValidation ? `<div class="why">Blind LLM says: ${{it.llm_correct ? 'correct' : 'incorrect'}} -- ${{escapeHtml(it.llm_type_reasoning)}}</div>` : ""}}
        </div>
        ${{(isControl || isValidation) ? "" : `
        <div class="proposal">
          <b>Blind LLM proposes</b>
          <div class="value">${{escapeHtml(it.llm_value ?? "(none)")}}</div>
          <div class="why">${{escapeHtml(it.facet === 'type' ? it.llm_type_reasoning : it.llm_format_reasoning)}}</div>
        </div>`}}
      </div>
      <div class="choices">
        ${{isValidation ? `
          <button class="kbd" data-key="1" onclick="choose('${{it.item_id}}','classifier')">&#10003; Correct location</button>
          <button class="kbd" data-key="2" onclick="choose('${{it.item_id}}','neither')">&#10007; Not actually this location</button>
        ` : isControl ? `
          <button class="kbd" data-key="1" onclick="choose('${{it.item_id}}','classifier')">&#10003; Correct</button>
          <button class="kbd" data-key="2" onclick="choose('${{it.item_id}}','neither')">&#10007; Wrong</button>
        ` : `
          <button class="kbd" data-key="1" onclick="choose('${{it.item_id}}','classifier')">Classifier is right: ${{escapeHtml(it.classifier_value ?? '')}}</button>
          <button class="kbd" data-key="2" onclick="choose('${{it.item_id}}','llm')">LLM is right: ${{escapeHtml(it.llm_value ?? '')}}</button>
          <button class="kbd" data-key="3" onclick="choose('${{it.item_id}}','neither')">Neither / other</button>
        `}}
      </div>
    </div>
  `;
}}

function escapeHtml(s) {{
  const d = document.createElement("div");
  d.textContent = s ?? "";
  return d.innerHTML;
}}

function choose(itemId, verdict) {{
  verdicts[itemId] = verdict;
  saveVerdicts(verdicts);
  render();
}}

document.addEventListener("keydown", (e) => {{
  const pending = pendingIndices();
  if (pending.length === 0) return;
  const it = ITEMS[pending[0]];
  const twoButton = it.facet === "location" || it.kind === "control";
  if (e.key === "1") choose(it.item_id, "classifier");
  else if (e.key === "2") choose(it.item_id, twoButton ? "neither" : "llm");
  else if (e.key === "3" && !twoButton) choose(it.item_id, "neither");
}});

document.getElementById("export").addEventListener("click", () => {{
  const blob = new Blob([JSON.stringify(verdicts, null, 2)], {{ type: "application/json" }});
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = "calibration_verdicts.json";
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}});

document.getElementById("reset").addEventListener("click", () => {{
  if (!confirm("Clear all progress on this device?")) return;
  verdicts = {{}};
  saveVerdicts(verdicts);
  render();
}});

render();
</script>
</body>
</html>
"""


def write_html(items: list[dict], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(render(items), encoding="utf-8")
