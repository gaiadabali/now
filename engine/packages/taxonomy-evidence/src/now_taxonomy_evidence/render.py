"""Render the assembled model to Markdown (the human surface) and JSON (E2.1's
input). Both read the same dict; neither computes anything.

Since 0.2.0 the model carries Hansel's resolutions (`resolution_meta`,
`decisions[].resolution`, `categories[].resolution`, `rules`). The renderer
reads them with `.get` so a pre-resolution model (the unit-test fixture, or an
old cache) still renders -- it just shows no resolution.
"""
from __future__ import annotations

import json


def _pct(x) -> str:
    return "-" if x is None else f"{100 * float(x):.0f}%"


def _fmt_dist(d: dict, k: int = 4) -> str:
    items = list(d.get("dist", {}).items())[:k]
    if not items:
        return "no signal"
    return ", ".join(f"{v} {_pct(s)}" for v, s in items) + f" (coverage {_pct(d.get('coverage'))})"


def _eff(p: dict, key: str) -> str:
    if key in (p.get("per_article") or []) or not p.get(key):
        return "*per article*"
    return f"`{p[key]}`"


def _prior(p: dict, key: str) -> str:
    """Like _eff but shows the prior value when the facet is per article with a prior."""
    if key in (p.get("per_article") or []):
        return f"*per article*" + (f" (prior `{p[key]}`)" if p.get(key) else "")
    return f"`{p[key]}`" if p.get(key) else "*per article*"


def _facets(p: dict) -> str:
    f = p.get("facets") or {}
    parts = [f"{k}: {', '.join(v) if isinstance(v, list) else v}" for k, v in f.items() if v]
    if p.get("series_key"):
        parts.append(f"series_key: `{p['series_key']}`")
    return "; ".join(parts) or "-"


def _esc(s: str) -> str:
    return (s or "").replace("|", "\\|").replace("\n", " ")


def _mapping(p: dict) -> str:
    return f"{_prior(p, 'type')}/{_prior(p, 'subtype')} + {_prior(p, 'format')} @ {_prior(p, 'location')}"


def render_json(model: dict) -> str:
    return json.dumps(model, ensure_ascii=False, indent=1)


def _render_rules(w, rules: dict) -> None:
    w("## 7. Classification rules for E2.1 — what the policy decisions produce")
    w("")
    w(f"Machine-readable twin: `rules` in `taxonomy-review.json` (decided by {rules.get('decided_by')} on {rules.get('decided_on')}). Together with `categories[].proposal` this is the whole prior E2.1 needs.")
    w("")
    pr = rules.get("prior_resolution", {})
    w(f"- **Prior resolution ({pr.get('decision')})** — order: {' → '.join(pr.get('order', []))}. {pr.get('note', '')}")
    gl = rules.get("guide_vs_listing", {})
    if gl:
        lw = gl.get("listing_when", {})
        w(f"- **Guide vs listing ({gl.get('decision')})** — `listing` when the title carries a period stamp ({'; '.join(lw.get('period_stamp', []))}) or the piece is a roundup: {gl['listing'].get('half_life_days')}-day half-life, `series_key` = {gl['listing'].get('series_key')}, rails: {gl['listing'].get('rails')}. Otherwise `guide` ({gl['guide'].get('when')}), evergreen. {gl.get('not_city_guide', '')}")
    le = rules.get("legacy_expiry", {})
    if le:
        w(f"- **Legacy expiry ({le.get('decision')})** — offer: {le['offer'].get('ends_at')}. event: {le['event'].get('ends_at')}. Expired: {le.get('expired')}.")
    pi = rules.get("print_issues", {})
    if pi:
        w(f"- **Print issues ({pi.get('decision')})** — facets from the category: {pi.get('facets_from_category')}; `series_key` {pi.get('series_key')}; format prior `{pi.get('format_prior')}`; {pi.get('everything_else')}.")
    co = rules.get("columns", {})
    if co:
        w(f"- **Columns ({co.get('decision')})** — `series_key` {co.get('series_key')}; migrated: {co.get('migrated')}; rails exclusion: {co.get('rails_exclusion')}; location: {co.get('location_fallback')}.")
    ms = rules.get("migration_scope", {})
    if ms:
        w(f"- **Migration scope ({', '.join(ms.get('decisions', []))})** — excluded categories: {ms.get('excluded_categories') or 'none'}; Uncategorized: {ms.get('uncategorized')}; non-articles: {ms.get('non_articles')}.")
    cg = rules.get("confidence_gate", {})
    if cg:
        w(f"- **Confidence gate** — auto-apply at ≥ {cg.get('auto_apply_at_or_above')}; below: {cg.get('below')} ({cg.get('source')}).")
    mc = rules.get("mixed_categories", {})
    if mc:
        w(f"- **Mixed categories (`{mc.get('id')}`)** — {mc.get('policy')} Rule: {mc.get('rule')}")
    loc = rules.get("location", {})
    if loc:
        w(f"- **Location** — required; site-home fallback {loc.get('site_home_fallback')}; {loc.get('syndication')}.")
        intl = loc.get("international", {})
        if intl:
            w("")
            w(f"### `international` ({intl.get('decision')}) — editorial-only, and how the engine encodes it")
            w("")
            w(f"- Term `{intl.get('term')}`; children: {intl.get('children')}.")
            w(f"- Attribute: `{intl.get('attribute', {}).get('key')}` = `{intl.get('attribute', {}).get('value')}`, inherited by descendants (default elsewhere: `{intl.get('attribute', {}).get('default_elsewhere')}`).")
            w(f"- Eligible: {', '.join(intl.get('eligible', []))}. Excluded: {', '.join(intl.get('excluded', []))}.")
            w(f"- Classifier rule: {intl.get('classifier_rule')}")
            w(f"- Subject rule: {intl.get('subject_rule')}")
            w(f"- Candidate rule: {intl.get('candidate_rule')}")
            enc = intl.get("encoding", {})
            for k in ("where", "enforced_by", "why_not_a_facet_flag", "why_not_rails_only_code", "prerequisite"):
                if enc.get(k):
                    w(f"- {k.replace('_', ' ').capitalize()}: {enc[k]}")
    w("")


def render_markdown(model: dict) -> str:
    city = model["city"]
    other = "bali" if city == "jakarta" else "jakarta"
    t = model["totals"]
    rm = model.get("resolution_meta")
    L: list[str] = []
    w = L.append
    w(f"# NOW! {city.title()} — taxonomy review: evidence pack" + (" (resolved)" if rm else ""))
    w("")
    if rm:
        w(f"**Status: RESOLVED — {rm['decided_by']}'s answers to all {rm['decisions_total']} decisions applied on {rm['decided_on']}; this file and its JSON twin are E2.1's input.** "
          f"Generated {model['generated']} by `{model['tool']}`. Builds on E1.4's draft (`jakarta/site/taxonomy-mapping.md`) and the E2.0 evidence (kept in full below: every instrument reading was taken against the E2.0 proposal, which each category still shows as `e20_proposal`). "
          f"The machine-readable twin `taxonomy-review.json` is rendered from the same in-memory model as this file.")
    else:
        w(f"**Status: evidence for the human review of blocker #3 (PROGRESS.md), generated {model['generated']} by `{model['tool']}`.** "
          f"Builds on E1.4's draft (`jakarta/site/taxonomy-mapping.md`); does not replace it. The machine-readable twin `taxonomy-review.json` is rendered from the same in-memory model as this file.")
    w("")
    w("## How to read this")
    w("")
    if rm:
        w(f"- **§1** lists the {t['decisions_for_city']} decisions that touch this city (of {rm['decisions_total']} across both cities; shared ids are identical in `{other}/site/taxonomy-review.md`) with the evidence, the E2.0 recommendation, and **the answer** — {len(rm['explicit'])} explicit ({', '.join(rm['explicit'])}), the rest the recommendation accepted as-is. Every conflict between an answer and a recommendation is stated under the decision, never reconciled silently.")
        w("- **§2** lists the categories the *data* flagged and how each flag was resolved (Hansel's answer for mixed categories: classify per article, no fixed category-wide type). **§3** is the coherence evidence, computed against the E2.0 proposal. **§4** is the vocabulary check; the reviewed change list lives in `engine/packages/taxonomy-evidence/vocabulary-delta.md`. **§5** calibrates the instruments. **§7** is the set of cross-cutting classifier rules the policy answers produce, including how `international` is encoded.")
        w(f"- **Appendix A** is every resolved mapping ({t['resolved_categories']} categories, the {t['changed_categories']} that changed against E2.0 first). **Appendix B** has the full evidence and the resolution for every category.")
    else:
        w(f"- **§1 is the whole job**: {t['decisions_for_city']} numbered decisions (of {t['decisions_total']} across both cities; the shared ones carry the same ID in `{other}/site/taxonomy-review.md`). Each has the evidence, a recommendation and the options. Confirm or override; nothing else needs reading unless you want to check the evidence.")
        w("- **§2** lists categories the *data* flagged beyond the registry (the cue instrument, the clusters or the LLM disagreed with the proposal). **§3** shows categories that are not one thing, with per-cluster examples. **§4** is the vocabulary check in both directions. **§5** calibrates the instruments so you know how much to trust them.")
        w(f"- **Appendix A** is the scannable list of auto-accepted categories ({t['auto_accepted_categories']} of {t['categories_with_articles']} with articles). **Appendix B** has the full evidence for every category, flagged ones first.")
    w(f"- Vectors for {city}: `{model['vector_source']}`." + (" **Weaker instrument**: TF-IDF/LSA is lexical, not semantic; coherence verdicts here are indicative." if "proxy" in model["vector_source"] else " Real `BAAI/bge-small-en-v1.5` article embeddings (filtered `WHERE model = :model`, F42)."))
    w(f"- LLM second opinion: {model['llm'].get('path')}. The LLM can only add flags; it never auto-accepts anything.")
    w("")
    w("### Counts")
    w("")
    rows = [("Articles", f"{t['articles']:,}"), ("Categories (with ≥1 published article)", f"{t['categories_with_articles']} of {t['categories']}")]
    if rm:
        rows += [
            (f"Decisions touching this city (resolved / total)", f"{t.get('decisions_resolved', 0)} / {t['decisions_for_city']}"),
            ("Categories still awaiting a decision", f"{t.get('decision_needed_categories', 0) + max(0, t['flagged_categories'] - t.get('decision_needed_categories', 0))}"),
            ("Categories resolved", f"{t.get('resolved_categories', 0)}"),
            ("… of which changed against the E2.0 proposal", f"{t.get('changed_categories', 0)}"),
            ("Categories that were flagged before resolution (decision-needed or by evidence)", f"{t.get('flagged_categories_pre_resolution', 0)}"),
        ]
    else:
        rows += [("Decisions needed (this city)", f"{t['decisions_for_city']}"), ("Categories flagged (decision-needed or flagged-by-evidence)", f"{t['flagged_categories']}"), ("Categories auto-accepted", f"{t['auto_accepted_categories']}")]
    rows.append(("Empty categories", f"{t['empty_categories']}"))
    w("| | |\n|---|---|")
    for k, v in rows:
        w(f"| {k} | {v} |")
    w("")

    # ---- §1 decisions ------------------------------------------------------
    w("## 1. Decisions — all resolved — ordered by articles affected" if rm else "## 1. Decisions needed — ordered by articles affected")
    w("")
    decisions = [d for d in model["decisions"] if city in d["cities"] or not d["cities"]]
    decisions.sort(key=lambda d: -d["articles_affected"])
    if rm:
        w("| # | decision | kind | articles | answer | source |\n|---|---|---|---:|---|---|")
        for d in decisions:
            r = d.get("resolution") or {}
            w(f"| {d['id']} | {_esc(d['title'])} | {d['kind']} | {d['articles_affected']:,} | {_esc(r.get('answer', ''))} | {r.get('source', '-')}{' ⚠ conflict' if r.get('conflicts') else ''} |")
    else:
        w("| # | decision | kind | articles | recommendation |\n|---|---|---|---:|---|")
        for d in decisions:
            w(f"| {d['id']} | {_esc(d['title'])} | {d['kind']} | {d['articles_affected']:,} | {_esc(d['recommendation'])} |")
    w("")
    for d in decisions:
        w(f"### {d['id']} · {d['title']}")
        w("")
        meta = [f"kind: {d['kind']}", f"articles affected: {d['articles_affected']:,}"]
        if d.get("carried_from"):
            meta.append(f"carried from {d['carried_from']}")
        if d["cities"]:
            meta.append("cities: " + ", ".join(d["cities"]))
        if d.get("status"):
            meta.append(f"status: {d['status']}")
        w(f"*{' · '.join(meta)}*")
        w("")
        w(f"**Question.** {d['question']}")
        w("")
        if d["affects"]:
            w("**Affects.** " + ", ".join(f"{a['city']}: {a['category']} ({a['articles']})" for a in d["affects"][:14]) + (" …" if len(d["affects"]) > 14 else ""))
            w("")
        if d["evidence"]:
            w("**Evidence.**")
            for e in d["evidence"]:
                w(f"- {e}")
            w("")
        w(f"**E2.0 recommendation.** {d['recommendation']}")
        w("")
        w("**Options.** " + " · ".join(d["options"]))
        w("")
        r = d.get("resolution")
        if r:
            w(f"**Resolved ({r['source']}, {r.get('decided_by', '')} {r.get('decided_on', '')}).** {r['answer']}")
            w("")
            w(f"*Option: {r['option']}.* {r.get('rationale', '')}")
            w("")
            if r.get("conflicts"):
                w("**Conflicts with the E2.0 recommendation (reported, not reconciled).**")
                for c in r["conflicts"]:
                    w(f"- ⚠ {c}")
                w("")
            if r.get("applies"):
                w("**Applied.** " + " · ".join(r["applies"]))
                w("")

    # ---- §2 evidence flags -----------------------------------------------
    w("## 2. Flagged by the evidence" + (" — and how each flag was resolved" if rm else " (beyond the registry)"))
    w("")
    if rm:
        efp = model.get("evidence_flag_policy") or {}
        w(f"Hansel's answer for mixed categories (`{efp.get('id')}`): **{efp.get('answer')}** {efp.get('rule', '')}")
        w("")
        flagged = [r for r in model["categories"] if r.get("e20_status") in ("decision-needed", "flagged-by-evidence") and r["flags"]]
        if not flagged:
            w("*No category was flagged by the evidence.*")
        for r in flagged:
            res = r.get("resolution") or {}
            w(f"- **{r['name']}** ({r['published']} articles; was `{r['e20_status']}`) — E2.0 proposal {_mapping(r['e20_proposal'])} → resolved **{_mapping(r['proposal'])}**. Basis: {', '.join(res.get('basis', []))}.")
            for f in r["flags"]:
                w(f"  - flag: {f}")
            if res.get("note"):
                w(f"  - resolution: {res['note']}")
        w("")
    else:
        w("Categories whose proposal the data contradicts. Each needs a one-line call: keep the proposal, or accept the alternate the evidence points at. Both are cheap; a silent wrong prior is not.")
        w("")
        ev = [r for r in model["categories"] if r["status"] == "flagged-by-evidence"]
        if not ev:
            w("*None — every auto-proposed mapping survived the cue instrument, the clusters and the LLM.*")
        for r in ev:
            p = r["proposal"]
            w(f"- **{r['name']}** ({r['published']} articles) — proposal {_eff(p, 'type')}/{_eff(p, 'subtype')} + {_eff(p, 'format')}:")
            for f in r["flags"]:
                w(f"  - {f}")
        w("")
        dn = [r for r in model["categories"] if r["status"] == "decision-needed" and r["flags"]]
        if dn:
            w("Decision-needed categories where the evidence also disagrees with the proposal (see the decision named in each):")
            w("")
            for r in dn:
                w(f"- **{r['name']}** ({', '.join(r['decisions'])}): " + " / ".join(r["flags"]))
            w("")

    # ---- §3 coherence ------------------------------------------------------
    w("## 3. Internal consistency — categories that are not one thing")
    w("")
    w(f"Vector space: `{model['vector_source']}`. A category is **incoherent** when k-means finds a split whose clusters read as different *venue* types while the proposal fixes one type (this changes competitor exclusion), or as formats with different decay classes while the proposal fixes one format — a split candidate, not a mapping problem. **mixed** is a weaker signal (clusters differ on non-venue types, or members sit closer to categories of another type). **expected-heterogeneous** means the proposal already leaves type per article (News, Events, containers, print issues), so heterogeneity is by design and the clusters are useful as classifier priors.")
    if rm:
        w("")
        w("Verdicts were computed against the **E2.0 proposal**. Where the resolution made the flagged facet per article, the split is now by design — marked *↳ resolved* below.")
    w("")
    cs = model["coherence_summary"]
    w(f"| verdict | categories |\n|---|---|")
    for k in ("incoherent", "mixed", "expected-heterogeneous", "coherent", "too-small", "n/a"):
        names = cs.get(k) or []
        if names:
            w(f"| {k} | {len(names)}: {', '.join(names[:18])}{' …' if len(names) > 18 else ''} |")
    w("")
    worst = [r for r in model["categories"] if r["coherence"] and r["coherence"]["verdict"] in ("incoherent", "mixed")]
    worst.sort(key=lambda r: (0 if r["coherence"]["verdict"] == "incoherent" else 1, -r["coherence"]["leakage"], -r["published"]))
    exp = [r for r in model["categories"] if r["coherence"] and r["coherence"]["verdict"] == "expected-heterogeneous" and r["coherence"]["clusters"] and r["published"] >= 40]
    for title, rows_ in (("### Split candidates", worst), ("### Expected-heterogeneous categories, largest first (clusters = classifier priors)", exp[:8])):
        w(title)
        w("")
        if not rows_:
            w("*none*")
            w("")
            continue
        for r in rows_:
            c = r["coherence"]
            p = r.get("e20_proposal") or r["proposal"]
            w(f"#### {r['name']} — {c['verdict']} · {r['published']} articles · E2.0 proposal {_eff(p, 'type')} + {_eff(p, 'format')}")
            w("")
            w(f"{c['reason']}. Cohesion {c['cohesion']} vs random baseline {c['baseline']} (ratio {c['cohesion_ratio']}); leakage {_pct(c['leakage'])}" + (" → " + ", ".join(f"{x['category']} ({x['articles']})" for x in c["confusable_with"]) if c["confusable_with"] else "") + ".")
            res = r.get("resolution") or {}
            if res.get("changed"):
                w("")
                w(f"*↳ resolved:* {_mapping(r['proposal'])} ({', '.join(res.get('basis', []))}).")
            w("")
            for i, cl in enumerate(c["clusters"], 1):
                w(f"- **Cluster {i}** — {cl['size']} articles ({_pct(cl['share'])}); cue type `{cl['top_type'] or '?'}` {_pct(cl['top_type_share'])}, cue format `{cl['top_format'] or '?'}` {_pct(cl['top_format_share'])}; words: {', '.join(cl['top_words'])}")
                for e in cl["examples"]:
                    w(f"  - {e['date']} · {_esc(e['title'])}")
            w("")

    # ---- §4 vocabulary -----------------------------------------------------
    v = model["vocabulary"]
    w("## 4. Vocabulary — the seed against the corpus, both directions")
    w("")
    w(f"Method: {v['method']}. Scanned {', '.join(f'{c} {n:,}' for c, n in v['articles_scanned'].items())} articles = {v['total_articles']:,}.")
    w("")
    vd = model.get("vocabulary_delta") or {}
    if vd.get("counts"):
        c_ = vd["counts"]
        w(f"**Resolved (D14/D15/D16/D22 — add every corpus term with ≥ 20 mentions):** the reviewed change list is `{vd.get('human')}` (machine twin `{vd.get('file')}`): "
          f"{c_['approve']} approvals of already-seeded proposed terms, **{c_['add_term']} terms to add** ({', '.join(f'{f} {n}' for f, n in c_['add_term_by_facet'].items())}), {c_['add_alias_sets']} alias sets ({c_['add_alias_forms']} forms), {c_['drop_term']} drop (`location/rawamangun`), {c_['trim_alias']} alias trims, {c_['merged']} merged and {c_['skipped']} skipped candidates; {c_['add_term_requiring_migration']} of the new terms need the F20 Payload ENUM migration. Nothing below has been written to the seed.")
        w("")
    w(f"### 4a. Seed terms that never appear ({len(v['seed_unused'])}) — removal candidates")
    w("")
    if v["seed_unused"]:
        w("| facet | slug | label | surface forms searched |\n|---|---|---|---|")
        for r in v["seed_unused"]:
            w(f"| {r['facet']} | `{r['slug']}`{' *(proposed)*' if r.get('proposed') else ''} | {_esc(r['label'])} | {_esc(', '.join(r['forms'][:6]))} |")
    else:
        w("*none*")
    w("")
    w(f"### 4b. Seed terms with fewer than 5 mentions ({len(v['seed_rare'])}) — keep only if a filter needs the value")
    w("")
    if v["seed_rare"]:
        w("| facet | slug | jakarta | bali |\n|---|---|---|---|")
        for r in v["seed_rare"]:
            w(f"| {r['facet']} | `{r['slug']}`{' *(proposed)*' if r.get('proposed') else ''} | {r['hits'].get('jakarta', 0)} | {r['hits'].get('bali', 0)} |")
    else:
        w("*none*")
    w("")
    w(f"### 4c. Frequent corpus terms with no seed term (≥ {v['candidate_threshold']} articles) — addition candidates" + (" (resolved: ≥ 20 added, see the delta)" if rm else ""))
    w("")
    by_facet: dict[str, list] = {}
    for r in v["candidates"]:
        by_facet.setdefault(r["facet"], []).append(r)
    for facet, rows_ in by_facet.items():
        rows_.sort(key=lambda r: -r["total"])
        w(f"**{facet}** — " + ", ".join(f"{r['label']}{'' if r['forms'][0].lower() == r['label'].lower() and len(r['forms']) == 1 else ' [' + ', '.join(r['forms'][:3]) + ']'} {r['total']} (j {r['hits'].get('jakarta', 0)} / b {r['hits'].get('bali', 0)}; titles {sum(r['title_hits'].values())})" for r in rows_[:30]))
        w("")
    w("Counts are lexical: `Java` also matches Java Jazz and coffee, `jungle` matches every jungle-view villa, `women` is not an audience segment until an editor says so. The title count is the stricter signal.")
    w("")
    alias = v.get("alias_suggestions") or []
    if alias:
        w(f"### 4c-bis. Alias suggestions for terms the seed already has (surface forms the seed lacks, ≥ {v['candidate_threshold']} articles)")
        w("")
        w("These are not missing terms — they are words the archive uses for a term that exists. Adding them as `aliases` improves the E2.1 prompt and the reader-filter matching.")
        w("")
        by_f: dict[str, list] = {}
        for r in alias:
            by_f.setdefault(r["facet"], []).append(r)
        for facet, rows_ in by_f.items():
            rows_.sort(key=lambda r: -r["total"])
            w(f"**{facet}** — " + ", ".join(f"{r['label']} ← {', '.join(r['forms'][:3])} ({r['total']})" for r in rows_[:20]))
            w("")
    w("### 4d. Seed coverage by facet (all seed terms, mentions per city)")
    w("")
    cur = None
    for r in v["seed_terms"]:
        if r["facet"] != cur:
            cur = r["facet"]
            w("")
            w(f"**{cur}** — " + ", ".join(f"`{x['slug']}` {x['total']}" for x in v["seed_terms"] if x["facet"] == cur))
    w("")
    w("### 4e. Editors' own tags with no seed coverage (post_tag vocabulary, WP counts ≥ 5)")
    w("")
    for c, rows_ in v["tags_uncovered"].items():
        w(f"**{c}** — " + (", ".join(f"{_esc(r['tag'])} {r['count']}" for r in rows_[:50]) or "none"))
        w("")

    # ---- §5 calibration ---------------------------------------------------
    w("## 5. How much to trust the instruments")
    w("")
    w("The cue instrument (title-weighted keyword scores; `text.py`) measured against categories whose mapping nobody disputes. Read the shares as the instrument's ceiling: when it says 45% of a disputed category is `offer`, compare with what it says for Dining Offers below. Known blind spots: `feature` has no lexical cue (it is the residual format), interviews and travel essays read as first-person, and Balinese culture explainers trip the `do` cues (temple, village, island). Flags in §2 are therefore raised only where the disagreement would change competitor exclusion (a venue type is involved) or the decay class (short / medium / evergreen).")
    w("")
    w("| city | category | n | claimed type | cue agrees | type coverage | claimed format | cue agrees | format coverage |\n|---|---|---:|---|---:|---:|---|---:|---:|")
    for r in model["instrument_calibration"]:
        w(f"| {r['city']} | {r['category']} | {r['n']} | {r['type'] or '-'} | {_pct(r['type_share'])} | {_pct(r['type_coverage'])} | {r['format'] or '-'} | {_pct(r['format_share'])} | {_pct(r['format_coverage'])} |")
    w("")
    w("Coherence: Jakarta uses real embeddings; Bali uses a TF-IDF/LSA proxy because `now_bali.engine.embeddings` is empty. The proxy sees words, not meaning — two restaurant reviews that share no vocabulary look unrelated to it. Treat Bali's `mixed` verdicts as prompts to look at the titles, not as findings.")
    w("")

    # ---- cross-city --------------------------------------------------------
    if model["cross_city"]:
        w("## 6. Cross-city consistency — categories both sites share" + (" (resolved priors)" if rm else ""))
        w("")
        w("A **conflict** is two fixed values that differ — a real inconsistency to resolve. **partial** means one city fixes the facet and the other leaves it per article because its articles are more mixed; that is deliberate and evidence-based, not drift.")
        w("")
        w("| category | jakarta (n) | jakarta type + format | bali (n) | bali type + format | verdict |\n|---|---|---|---|---|---|")
        for x in model["cross_city"]:
            v_ = x.get("verdict", "same" if x["consistent"] else "conflict")
            w(f"| {x['category']} | {x['jakarta']['name']} ({x['jakarta']['articles']}) | {x['jakarta']['type']} + {x['jakarta']['format']} | {x['bali']['name']} ({x['bali']['articles']}) | {x['bali']['type']} + {x['bali']['format']} | {'same' if v_ == 'same' else ('**CONFLICT** — ' if v_ == 'conflict' else 'partial — ') + _esc(x['note'])} |")
        w("")

    # ---- §7 rules ----------------------------------------------------------
    if model.get("rules"):
        _render_rules(w, model["rules"])

    # ---- Appendix A ---------------------------------------------------------
    if rm:
        w("## Appendix A. Resolved mappings — every category with articles, changed first")
        w("")
        w("`proposal` in the JSON is the resolved prior E2.1 reads; `e20_proposal` is what the evidence was gathered against. *per article* means the classifier decides, with the prior shown in brackets where one exists.")
        w("")
        w("| category | n | resolved type/subtype | format | location | other | conf. | basis | changed vs E2.0 | status |\n|---|---:|---|---|---|---|---|---|---|---|")
        for r in model["categories"]:
            if not (r["status"] or "").startswith("resolved"):
                continue
            p = r["proposal"]
            res = r.get("resolution") or {}
            ch = res.get("changes") or {}
            chs = "; ".join(f"{k}: {v['from']} → {v['to']}" if k != "facets" else "facets: " + ", ".join(f"{fk} {fv['from']} → {fv['to']}" for fk, fv in v.items()) for k, v in ch.items()) or "-"
            w(f"| {_esc(r['name'])} | {r['published']} | {_prior(p, 'type')}/{_prior(p, 'subtype')} | {_prior(p, 'format')} | {_prior(p, 'location')} | {_esc(_facets(p))} | {r['confidence']} | {', '.join(res.get('basis', []))} | {_esc(chs)} | {_esc(r['status'])} |")
        w("")
    else:
        w("## Appendix A. Auto-accepted mappings (scannable)")
        w("")
        w("Accepted because E1.4 (Jakarta) or the evidence-pack proposal (Bali) fixes the mapping at high or medium confidence with no open category-specific decision, the cue instrument does not contradict it, the clusters do not split it, and the LLM (when used) agreed. Some depend on a vocabulary/policy decision in §1 — the status says which.")
        w("")
        w("| category | n | years | type/subtype | format | location | other | conf. | cue support | coherence | status |\n|---|---:|---|---|---|---|---|---|---|---|---|")
        for r in model["categories"]:
            if not (r["status"] or "").startswith("auto-accepted"):
                continue
            p = r["proposal"]
            tc = r["cues"]["type"]["dist"].get(p["type"]) if p["type"] else None
            fc = r["cues"]["format"]["dist"].get(p["format"]) if p["format"] else None
            support = " / ".join(x for x in [f"type {_pct(tc)}" if tc is not None else None, f"format {_pct(fc)}" if fc is not None else None] if x) or "-"
            cohv = r["coherence"]["verdict"] if r["coherence"] else "-"
            w(f"| {_esc(r['name'])} | {r['published']} | {r['first_year']}–{r['last_year']} | {_eff(p, 'type')}/{_eff(p, 'subtype')} | {_eff(p, 'format')} | {_eff(p, 'location')} | {_esc(_facets(p))} | {r['confidence']} | {support} | {cohv} | {_esc(r['status'])}{(' — ' + ', '.join(r['decisions'])) if r['decisions'] else ''} |")
        w("")

    # ---- Appendix B ---------------------------------------------------------
    w("## Appendix B. Per-category evidence" + (" and resolution — changed first, then by size" if rm else " — flagged first, then by size"))
    w("")
    for r in model["categories"]:
        p = r["proposal"]
        w(f"### {r['name']} — {r['status']}")
        w("")
        meta = [f"{r['published']} published" + (f" (WP count {r['wp_count']})" if r["wp_count"] not in (None, r["published"]) else ""),
                f"{r['first_year']}–{r['last_year']}" if r["first_year"] else "no articles",
                f"parent: {r['parent']}" if r["parent"] else "top-level",
                f"Yoast primary on {r['yoast_primary']}", f"slug `{r['slug']}`", f"term {r['term_id']}"]
        w("*" + " · ".join(meta) + "*")
        w("")
        if r["description"]:
            w(f"> Editor's description: {_esc(r['description'][:300])}")
            w("")
        if r["published"] == 0:
            w("No published articles carry this category. Nothing to map.")
            w("")
            continue
        res = r.get("resolution")
        label = "**Resolved prior**" if res else "**Proposal**"
        w(f"{label} ({r['proposal_source']}): type {_prior(p, 'type')} · subtype {_prior(p, 'subtype')} · format {_prior(p, 'format')} · location {_prior(p, 'location')} · {_facets(p)} · confidence **{r['confidence']}**" + (f" · decisions {', '.join(r['decisions'])}" if r["decisions"] else ""))
        w("")
        if res:
            e20 = r.get("e20_proposal") or p
            if res.get("changed"):
                w(f"**E2.0 proposal (before the answers).** type {_prior(e20, 'type')} · subtype {_prior(e20, 'subtype')} · format {_prior(e20, 'format')} · location {_prior(e20, 'location')} · {_facets(e20)} · status was `{r.get('e20_status')}`.")
                w("")
            w(f"**Resolution.** basis {', '.join(res.get('basis', []))}; {'changed' if res.get('changed') else 'unchanged'}" + (f" — {_esc(res['note'])}" if res.get("note") else "") + (f"; addressed flags: {len(res.get('addressed_flags') or [])}" if res.get("addressed_flags") else "") + ".")
            w("")
        w(f"**Reasoning.** {_esc(r['reasoning'])}")
        w("")
        if r["alternates"]:
            w("**Alternates for the classifier.** " + "; ".join(_esc(a) for a in r["alternates"]))
            w("")
        if r["flags"]:
            w("**Flags (evidence against the E2.0 proposal).** " + " / ".join(r["flags"]))
            w("")
        w("**Representative titles (spread across the date range).**")
        for s in r["samples"]:
            w(f"- {s['date']} · {_esc(s['title'])}")
        w("")
        w(f"**Cue instrument.** type: {_fmt_dist(r['cues']['type'])}; format: {_fmt_dist(r['cues']['format'])}; period-stamped titles {_pct(r['period_stamped_share'])}; roundups {_pct(r['roundup_share'])}; median first-person density {r['fp_density_median']}/1000 words.")
        w("")
        loc = r["locations"]
        if loc["top"]:
            w(f"**Places named in title/lead.** " + ", ".join(f"{x['slug']} {x['articles']}" for x in loc["top"]) + f"; {_pct(loc['outside_home_share'])} name only a place outside {city}.")
            w("")
        if r["cooccurs"]:
            w("**Co-filed with.** " + ", ".join(f"{x['category']} {x['articles']}" for x in r["cooccurs"]) + f"; {r['single_category_articles']} carry this category alone.")
            w("")
        c = r["coherence"]
        if c and c["verdict"] not in ("too-small", "n/a"):
            w(f"**Coherence** ({c['verdict']}, against the E2.0 proposal). {c['reason']}. Cohesion {c['cohesion']} (baseline {c['baseline']}), leakage {_pct(c['leakage'])}" + (" → " + ", ".join(f"{x['category']} ({x['articles']})" for x in c["confusable_with"]) if c["confusable_with"] else "") + f"; best split k={c['best_k']} silhouette {c['silhouette']}.")
            for i, cl in enumerate(c["clusters"], 1):
                w(f"- cluster {i}: {cl['size']} ({_pct(cl['share'])}) `{cl['top_type'] or '?'}`/`{cl['top_format'] or '?'}` — " + "; ".join(_esc(e["title"][:70]) for e in cl["examples"][:3]))
            w("")
        elif c:
            w(f"**Coherence.** {c['reason']}.")
            w("")
        if r["llm"] and r["llm"].get("result"):
            x = r["llm"]["result"]
            w(f"**LLM second opinion** ({r['llm'].get('model')}, against the E2.0 proposal): type `{x.get('type')}` · subtype `{x.get('subtype')}` · format `{x.get('format')}` · location `{x.get('location')}` · agrees: {x.get('agree_with_proposal')} · split: {x.get('split_recommended')}{(' → ' + ', '.join(x.get('split_into') or [])) if x.get('split_recommended') else ''} · confidence {x.get('confidence')}. {_esc(x.get('rationale', ''))}")
            w("")
        if r["e14"]:
            e = r["e14"]
            w(f"**E1.4 draft.** confidence {e.get('confidence')}, decision_needed {e.get('decision_needed')}" + (f" — {_esc(e.get('decision'))}" if e.get("decision") else ""))
            w("")
    w("---")
    w(f"*Generated from one in-memory model by `now-taxonomy-evidence build`; regenerate rather than hand-edit. Answers live in `src/now_taxonomy_evidence/resolutions.py`; cache: `engine/packages/taxonomy-evidence/.cache/`.*")
    return "\n".join(L) + "\n"
