"""Hansel's answers to the 27 taxonomy decisions (2026-09-10) and what they change.

This is the ONLY place the answers are written down. `proposals.py` stays the
E2.0 record (the proposal the evidence was gathered against -- features,
coherence and the cached LLM prompts all key off it); `decide.py` applies the
tables below *after* the evidence phase, so every rendered category carries
both the E2.0 proposal (`e20_proposal`) and the resolved prior (`proposal`,
the field E2.1 reads).

Three tables:

* RESOLUTIONS            one entry per id in `proposals.DECISIONS`: the
                         operative answer, which listed option it is, whether
                         it was an explicit answer or the recommendation
                         accepted as-is, and every conflict with the
                         recommendation (reported, never silently reconciled).
* EVIDENCE_FLAG_POLICY   the explicit answer that covers the Section 2 evidence
                         flags ("mixed categories -> classify per article").
* CATEGORY_RESOLUTIONS   the per-category overrides the answers imply.
* RULES                  the cross-cutting classifier rules the policy
                         decisions produce -- machine-readable, for E2.1.

Eight answers were explicit (D01, D02, D06, D09/D08, D10, D14/D15/D16/D22,
D21, D26 plus the mixed-categories answer); the other nineteen accept the
E2.0 recommendation. Where an explicit answer and a recommendation conflict,
the explicit answer wins and the conflict is recorded in `conflicts`.

Follow-up round (same day, 2026-09-10): E2.0b's first pass surfaced four
ambiguities in the answers above; Hansel resolved all four. None of the four
is a new decision id -- each amends an existing one (D06, D08, D09, D14) --
so `RESOLUTIONS`'s key set (one entry per registry decision) is unchanged.
What changed:

1. D08 -- the "keep all, no exclusions" answer is narrowed back to the
   original recommendation's rails exclusion, but only for the two
   no-local-subject columns (Must Watch Movies, Music to the Ears); the
   ORIGINAL conflict text is kept (not rewritten) and a new entry records the
   supersession, per the "report, never silently reconcile" rule. See
   `RULES["columns"]["excluded_from_rails"]` for the mechanism.
2. D09 -- confirmed as already applied: no special-casing for the five
   page-like Uncategorized titles. Nothing changes; see the check in
   `test_resolutions.py` and `NON_ARTICLE_TITLES_KEPT` below.
3. D14 -- confirmed as already applied: the four sub-threshold location terms
   (belitung 18, bintan 18, lake-toba 16, cibubur 13) are kept, closing the
   open question the original D14 conflict note left hanging.
4. D06 -- `international` also suppresses Row 1 (complementary places), not
   only Row 2 (nearby) and the itinerary; `RULES["location"]["international"]`
   is updated and the previously-"inferred" Row 1 suppression is now marked
   answered. Indonesian cities under the flat `other` root are approved for
   re-parenting under their island region node (`parent_id` only) -- recorded
   in `RULES["location"]["reparenting"]` for the seed ticket running in
   parallel this wave; NOT applied here (out of this package's scope).
"""
from __future__ import annotations

DECIDED_BY = "Hansel"
DECIDED_ON = "2026-09-10"

# Titles of the five obvious non-article pages D09's recommendation would have
# excluded; kept (migrated, classified best-effort) under the explicit answer.
NON_ARTICLE_TITLES_KEPT = [
    "Order Form - NOW! Magazines",
    "USA NATIONAL DAY",
    "French National Day 12 July 2019 at Raffles Jakarta",
    "SWISS NATIONAL DAY",
    "Purchasing NOW! Bali & TIMELESS Bali Magazines",
]

RESOLUTIONS: dict[str, dict] = {
    "D01": {
        "source": "explicit", "option": "adopt",
        "answer": "Period-stamped roundups (a year in the title, '[Updated]', a seasonal marker) are `listing`: 540-day half-life, a `series_key`, and only the current member of a series is eligible in any rail. Timeless how-to and area pieces stay evergreen `guide`.",
        "rationale": "Lets the 2019 editions sink while the current '[Updated]' edition stays fresh through series dedup; `guide` is reserved for pieces that do not date.",
        "conflicts": [],
        "applies": ["rules.guide_vs_listing", "no category changes -- every Guide category already leaves format per article with D01 as the tie-breaker"],
    },
    "D02": {
        "source": "explicit", "option": "accept 90/30",
        "answer": "Extract the real end date from the text where one is present; otherwise an offer expires at publish + 90 days and an event at publish + 30 days. Expired items stay searchable and never enter a rail.",
        "rationale": "Almost every offer before 2024 is dead anyway; the windows only matter for recent, undated ones.",
        "conflicts": [],
        "applies": ["rules.legacy_expiry"],
    },
    "D03": {
        "source": "as-recommended", "option": "approve",
        "answer": "Approve the `opinion` format (540-day half-life).",
        "rationale": "Columns date like reviews, not like guides; `feature` would keep 2016 columns permanently fresh.",
        "conflicts": [],
        "applies": ["vocabulary-delta: approve format/opinion (already seeded as proposed and already a value of enum_articles_format -- no migration)"],
    },
    "D04": {
        "source": "as-recommended", "option": "approve",
        "answer": "Approve the `editorial/culture` subtype.",
        "rationale": "~870 articles across both cities have no honest node without it.",
        "conflicts": [],
        "applies": ["vocabulary-delta: approve subtype/culture (already seeded; already in enum_places_subtype)"],
    },
    "D05": {
        "source": "as-recommended", "option": "approve",
        "answer": "Approve the `editorial/lifestyle` subtype.",
        "rationale": "Service journalism with no venue subject otherwise force-fits into `news`.",
        "conflicts": [],
        "applies": ["vocabulary-delta: approve subtype/lifestyle (already seeded; already in enum_places_subtype)"],
    },
    "D06": {
        "source": "explicit", "option": "approve",
        "answer": "Add the `international` location root, editorial-only: searchable and eligible for Row 3 (related reading); never Row 1 (complementary places), never Row 2 (nearby), never the itinerary builder.",
        "rationale": "`location` is required and 115+ articles are about destinations abroad; they are worth reading next to a travel piece but can never be a nearby or complementary place, nor on an itinerary.",
        "conflicts": [
            "The recommendation seeded `international` as a single leaf with children added 'once E2.1 reports the destination distribution'. The vocabulary answer (every corpus term with >= 20 mentions) adds 22 destination children now (see vocabulary-delta.json); the explicit answer wins. Children inherit the root's editorial-only attribute.",
        ],
        "applies": ["rules.location.international (encoding: term attribute geo_scope=abroad, enforced by the geo-anchored consumers)", "vocabulary-delta: approve location/international with attrs.geo_scope=abroad; add 22 children", "jakarta World Traveller keeps location international; jakarta Travel and bali Travel may pick it per article"],
        "follow_up": {
            "id": 4, "decided_on": "2026-09-10",
            "question": "Does `international` also suppress Row 1 (complementary places)? Should Indonesian cities under `other` be re-parented under island regions?",
            "answer": "Both. A Paris feature has no local subject place, so Row 1 has the exact same problem Row 2 does -- both rails are now suppressed the same way (subject_abroad short-circuit, Row 3 and search unaffected). Re-parenting: approved -- `parent_id` only, no other field changes. This pack was previously silent on Row 1 (it read the answer as inferred, not explicit) and on re-parenting (an open question in vocabulary_delta.py's notes); both are now answered.",
            "applies": ["rules.location.international.excluded now lists row1_complementary alongside row2_nearby and the itinerary builder, marked answered not inferred", "rules.location.reparenting -- approved, NOT applied by this package; the seed ticket running in parallel this wave applies it"],
        },
    },
    "D07": {
        "source": "as-recommended", "option": "confirm",
        "answer": "Print-issue categories carry no facets: `series_key = issue:<slug>`, format prior `feature`, everything else from content.",
        "rationale": "One decision retires 34 categories that were themes of individual 2019-2020 issues.",
        "conflicts": [],
        "applies": ["rules.print_issues", "34 Jakarta print-issue categories resolved"],
    },
    "D08": {
        "source": "explicit", "option": "keep all, migrated and searchable; rails-excluded for the two no-local-subject columns (follow-up #1, 2026-09-10, narrows the first answer's 'no exclusions')",
        "answer": "Keep every column category and migrate all of it -- including Must Watch Movies (13) and Music to the Ears (11), which have no Bali subject. `series_key = column:<slug>` for every column. Follow-up #1: nothing is discarded and both columns stay fully searchable, but Must Watch Movies and Music to the Ears must not be recommended alongside local content -- the rails exclusion E2.0's original recommendation had is restored for exactly these two series. Every other column (Chaine Des Rottiseurs, Cook and Mix, Health & Wellness, Home Life, ...) keeps the original 'nothing excluded' answer unchanged.",
        "rationale": "Hansel: migrate everything, classify best-effort. Follow-up: 'migrate everything' was about not discarding content, not about making no-local-subject columns compete with local recommendations -- restoring the original recommendation's exclusion for exactly these two columns satisfies both without touching the other columns' rails eligibility.",
        "conflicts": [
            "ORIGINAL (2026-09-10): the recommendation excluded the two no-local-subject columns from the rails via the quality floor. The first answer ('nothing excluded') removed that exclusion entirely and is applied as written in that round's pack.",
            "SUPERSEDED same day by follow-up #1: the exclusion is restored for Must Watch Movies and Music to the Ears specifically, via a series-level hard-filter rule (not the quality floor -- see `RULES['columns']['excluded_from_rails']` for the mechanism and why). This is reported, not silently reconciled: the two rounds' packs will differ on this point if compared.",
            "The four location-less columns (Must Watch Movies, Music to the Ears, Health & Wellness, Home Life) had `location: none` in the E2.0 proposal; `location` is a required facet, so the resolved prior is the site home (`bali`) -- the same fallback E1.4 uses for Jakarta (`location_when_unspecified`). This is independent of rails eligibility: the location prior still applies to all four; only Must Watch Movies and Music to the Ears lose rails eligibility.",
        ],
        "applies": ["rules.columns", "rules.columns.excluded_from_rails (Must Watch Movies, Music to the Ears -- series-level rails exclusion, follow-up #1)", "bali: Must Watch Movies, Music to the Ears, Health & Wellness, Home Life -> location prior bali", "bali: Chaine Des Rottiseurs and Cook and Mix resolved under the mixed-categories answer (see the category records)"],
    },
    "D09": {
        "source": "explicit", "option": "migrate all; classifier at the normal threshold (neither listed option verbatim)",
        "answer": "Migrate everything and classify best-effort: no prior from Uncategorized, the classifier decides every facet, and the standard E2.1 confidence gate applies (below the auto-apply threshold -> review queue, never written as fact). Nothing is excluded.",
        "rationale": "Hansel: migrate everything, nothing excluded -- including Uncategorized (154). The confidence gate is the standard path, not an override.",
        "conflicts": [
            "The recommendation sent every Uncategorized post to the review queue regardless of confidence; the answer uses the standard gate, so high-confidence classifications auto-apply.",
            "The recommendation excluded obvious non-articles below the quality floor; the answer excludes nothing. Five titles are pages rather than editorial (" + "; ".join(f"'{t}'" for t in NON_ARTICLE_TITLES_KEPT) + "). They will be classified best-effort and will most likely land in the review queue on low confidence, where an editor can unpublish them. Cheap to reverse -- flagged for a second look.",
        ],
        "applies": ["rules.migration_scope", "rules.confidence_gate", "jakarta + bali Uncategorized resolved: no prior, per-article everything"],
        "follow_up": {
            "id": 2, "decided_on": "2026-09-10",
            "question": "Should the five page-like items (Order Form, magazine-purchasing page, three national-day announcements) get a carve-out instead of best-effort classification?",
            "answer": "No carve-out. Classify best-effort like everything else -- the 0.85 confidence gate (rules.confidence_gate) routes them to the review queue naturally, same as any other low-confidence item.",
            "confirmed": "no special-casing exists in decide.py, proposals.py or resolutions.py for NON_ARTICLE_TITLES_KEPT beyond this documentation list -- it is not read by any classifier code path, only carried here and in the D09 conflict text above for traceability.",
        },
    },
    "D10": {
        "source": "explicit", "option": "adopt",
        "answer": "Prior resolution order for a multi-category post: the Yoast primary category, else the deepest (most specific) child category, else the parent container.",
        "rationale": "Makes the eleven container categories mostly moot; Bali has a Yoast primary on 82% of posts, Jakarta on 44%.",
        "conflicts": [],
        "applies": ["rules.prior_resolution"],
    },
    "D11": {
        "source": "as-recommended", "option": "approve",
        "answer": "Approve `do/sports-activity`; the classifier picks among do/sports-activity, event/sports and an editorial feature per article.",
        "rationale": "Participatory sport venues have no other node.",
        "conflicts": [],
        "applies": ["vocabulary-delta: approve subtype/sports-activity (already seeded; already in enum_places_subtype)"],
    },
    "D12": {
        "source": "as-recommended", "option": "approve all",
        "answer": "Approve the event subtypes `performance`, `screening` and `pop-up`.",
        "rationale": "Theatre/dance, film festivals and pop-up markets have no Section 4 node.",
        "conflicts": [],
        "applies": ["vocabulary-delta: approve subtype/performance, screening, pop-up (already seeded; already in enum_places_subtype)"],
    },
    "D13": {
        "source": "as-recommended", "option": "approve both",
        "answer": "Approve the wellness subtypes `salon` and `retreat`.",
        "rationale": "`spa` would absorb beauty venues and multi-day retreats and blur Row 1 matching.",
        "conflicts": [],
        "applies": ["vocabulary-delta: approve subtype/salon, retreat (already seeded; already in enum_places_subtype)"],
    },
    "D14": {
        "source": "explicit", "option": "flat >= 20 for additions (replaces the recommendation's 10 / 20 / 5 thresholds); drop rawamangun",
        "answer": "Add every corpus location term with >= 20 mentions (Bali 14, elsewhere in Indonesia 12, international 22, Jakarta 11 candidates -- vocabulary-delta.json lists each with its counts and the node-vs-alias call); below 20 stays out. Drop `location/rawamangun` (2 mentions). Trim the homonym-inflated aliases `Batu` (malang) and `Wijaya` (gunawarman); title-case-only matching for `solo` and `kuningan`.",
        "rationale": "Hansel: add every corpus term with >= 20 mentions, drop rawamangun, trim the homonym aliases the pack identified.",
        "conflicts": [
            "The recommendation used three thresholds (approve proposed nodes >= 10, add gaps >= 20, drop proposed nodes < 5). The answer is a flat >= 20 for additions plus one named drop. Already-seeded proposed nodes with 5-19 mentions (belitung 18, bintan 18, lake-toba 16, cibubur 13) are KEPT here because only rawamangun was named -- if 'below 20 stays out' was meant to cover existing proposed nodes too, these four are a one-line removal in the seed ticket.",
        ],
        "applies": ["vocabulary-delta: approve the 35 remaining proposed location nodes; add 54 location terms (Bali 10 incl. a new west-bali district, elsewhere-in-Indonesia 12 region/city leaves under `other`, international 22, Jakarta 10) and 9 alias sets; drop rawamangun; trim malang/Batu, gunawarman/Wijaya + Kebayoran Baru, nusa-penida/Nusa Lembongan + Nusa Ceningan"],
        "follow_up": {
            "id": 3, "decided_on": "2026-09-10",
            "question": "The four sub-threshold already-seeded nodes above (belitung 18, bintan 18, lake-toba 16, cibubur 13) -- keep or drop?",
            "answer": "Keep them. The >= 20 rule applied to the 217 new candidates the corpus scan surfaced; these four were already vetted and seeded by the earlier E1.4/E2.0 pass, not proposed fresh by this scan, so the threshold does not re-litigate them.",
            "resolves": "the open question the conflict entry above left hanging -- this is not a one-line removal; vocabulary-delta.json and both packs already keep all four (verified: they are absent from `drop_term` and present as approved nodes), so no further change is needed.",
        },
    },
    "D15": {
        "source": "explicit", "option": "apply thresholds (>= 20), dietary needs stay in amenities",
        "answer": "Add every corpus cuisine term with >= 20 mentions. Dietary and approach terms (organic, healthy, vegetarian, vegan, gluten-free, farm-to-table) are routed to amenities, as the seed designed and the recommendation kept. No seed cuisine is removed (none has < 10 mentions).",
        "rationale": "Hansel's flat >= 20 rule; the amenities routing is the accepted recommendation.",
        "conflicts": [],
        "applies": ["vocabulary-delta: 12 new cuisine terms, 10 cuisine alias sets, 3 dietary/approach terms routed to amenities (organic, healthy-menu, gluten-free) plus vegetarian/vegan as alias sets on the existing amenities; trim american/BBQ and chinese/hotpot (now their own cuisines)"],
    },
    "D16": {
        "source": "explicit", "option": "apply (>= 20)",
        "answer": "Add every vibe, occasion, amenity, audience and topic corpus term with >= 20 mentions (duplicates merged: Retiree into seniors, the two wedding topics into one, Rice terrace + Hot spring + Waterfall into do/nature). Nothing is pruned -- no seed term has zero support. Trim the homonym aliases `party` (occasion/celebration) and `business` (audience/business-traveller).",
        "rationale": "Hansel's flat >= 20 rule plus the named alias trims.",
        "conflicts": [],
        "applies": ["vocabulary-delta: vibe 12 terms + 9 alias sets, occasion 8 terms + 5 alias sets, amenities 23 terms (3 routed from cuisine) + 8 alias sets, audience 9 terms + 6 alias sets, topic 11 terms + 16 alias sets"],
    },
    "D17": {
        "source": "as-recommended", "option": "accept",
        "answer": "Experience Offers (both cities): format `offer` fixed; type per article with `stay/hotel` as the prior; the classifier may pick eat, wellness, do or event. Not a `do` category.",
        "rationale": "Hotel experience marketing where the subject is often the hotel's restaurant or spa.",
        "conflicts": [],
        "applies": ["no change -- already the proposal in both cities"],
    },
    "D18": {
        "source": "as-recommended", "option": "accept",
        "answer": "Explore Bali is a container (D10): no type prior of its own, children carry the priors; Explore Bali + Opinion -> editorial/opinion.",
        "rationale": "41 of 117 co-occur with Opinion; the rest are the parent of Activities/Cultural Sites/Destinations.",
        "conflicts": [],
        "applies": ["no change"],
    },
    "D19": {
        "source": "as-recommended", "option": "feature prior for both",
        "answer": "Community (both cities): format prior `feature`; the classifier switches to `event` (dated fundraisers) or `news` (announcements) when the text says so; topic `community` always.",
        "rationale": "NGO and initiative features are evergreen, not 21-day news.",
        "conflicts": [],
        "applies": ["no change -- E2.0 already amended Jakarta Community to feature; Bali proposal already feature"],
    },
    "D20": {
        "source": "as-recommended", "option": "offer prior, per-article override",
        "answer": "Bali Dining Offers: format per article with `offer` as the prior (the Yoast primary decides when Restaurants and Bars is primary); roughly a third will be relabelled news.",
        "rationale": "Bali's offer cue is weak (45%); many 2016-2019 pieces are menu/opening write-ups filed as offers.",
        "conflicts": [],
        "applies": ["no change"],
    },
    "D21": {
        "source": "explicit", "option": "accept",
        "answer": "Bali News (1,067): format `news` as the prior, type per article. Roughly a quarter will be relabelled event/offer by the classifier -- intended.",
        "rationale": "Same treatment E1.4 gave Jakarta News; the single largest lever on Bali's freshness curve.",
        "conflicts": [],
        "applies": ["no change"],
    },
    "D22": {
        "source": "explicit", "option": "add occasion/wedding",
        "answer": "Add `occasion/wedding` (aliases weddings, honeymoon, proposal, bridal, bachelorette, hen party). The Bali Weddings category carries occasion `wedding` instead of `celebration`.",
        "rationale": "A real reader intent in Bali (220 corpus mentions); part of Hansel's >= 20 vocabulary answer.",
        "conflicts": [],
        "applies": ["vocabulary-delta: add occasion/wedding", "bali Weddings: facets.occasion -> [wedding]"],
    },
    "D23": {
        "source": "as-recommended", "option": "accept",
        "answer": "Bali Lifestyle is a container (D10): the child's prior wins; for the residue type and format per article with editorial/lifestyle as the fallback.",
        "rationale": "242 of 243 also carry a child category.",
        "conflicts": [],
        "applies": ["no change"],
    },
    "D24": {
        "source": "as-recommended", "option": "accept the split as proposed",
        "answer": "Bali Culture family: Bali History and Myths and Legends -> editorial/heritage + heritage; Cultural Observer, Dance and Music, Ceremonies & Festivals, Everyday Bali, Culture -> editorial/culture + feature. Stranger In Paradise keeps editorial/opinion as its prior with format per article (heritage as the alternate).",
        "rationale": "Both formats are evergreen so decay is unaffected; the split decides which reader filter the pieces surface under.",
        "conflicts": [
            "E2.0's own output is inconsistent for Stranger In Paradise: the D24 question text lists it under editorial/heritage + heritage, while the proposal table has editorial/opinion + opinion (the LLM second opinion and the first-person density agree with opinion). Resolved as opinion prior, format per article with heritage as the alternate -- the clusters split 57/43 between medium and evergreen decay.",
        ],
        "applies": ["bali Stranger In Paradise: format per article"],
    },
    "D25": {
        "source": "as-recommended", "option": "accept",
        "answer": "Jakarta Art and Bali Art In Bali: no type/format prior; topic `art`; the classifier decides among the listed alternates.",
        "rationale": "Both mix dated exhibitions, artist profiles, commentary and buying guides.",
        "conflicts": [],
        "applies": ["no change"],
    },
    "D26": {
        "source": "explicit", "option": "accept type-switchable prior; format per article -- strengthened to type per article",
        "answer": "Jakarta Business: type per article -- no fixed category-wide type. editorial/business stays the prior; stay/hotel or eat/restaurant when a venue is the subject; format per article.",
        "rationale": "Hansel: classify mixed categories per article; a fixed `editorial` type would leave hotel corporate announcements un-excluded on competitor pages.",
        "conflicts": [],
        "applies": ["jakarta Business: per_article type, subtype, format"],
    },
    "D27": {
        "source": "as-recommended", "option": "confirm",
        "answer": "Features (3), Home Life (1) and Offers (1) are classified from content; Mapping Bali and Archives are empty containers with nothing to map.",
        "rationale": "0-3 published posts each.",
        "conflicts": [],
        "applies": ["no change"],
    },
}

# Hansel's answer to the Section 2 evidence flags (and D26): "Classify per-article,
# no fixed category-wide type. Protects competitor exclusion." Applied to every
# category the evidence flagged, on the flagged facet.
EVIDENCE_FLAG_POLICY: dict = {
    "id": "mixed-categories",
    "source": "explicit",
    "answer": "Classify per article; no fixed category-wide type where the evidence shows a venue-type mix. Protects competitor exclusion.",
    "rule": "The flagged facet becomes per-article. The E2.0 value stays the prior unless the cue instrument gives it <= 10% support against >= 50% for the alternate, in which case the alternate becomes the prior (Chaine Des Rottiseurs: event 0% vs review 50% -> prior review). Type flags where the instrument is fooled by vocabulary (Cook and Mix: recipes read as `eat`) still go per-article, with an explicit classifier note, because the E2.1 confidence gate catches a wrong `eat` and a false exclusion is the cheap error.",
    "applies_to": [
        {"city": "jakarta", "category": "Reviews", "flag": "cluster 23% drink (wine, beer, coffee pieces)", "resolution": "type + subtype per article; prior eat/restaurant; format review fixed"},
        {"city": "jakarta", "category": "Features", "flag": "cue type eat 50%", "resolution": "type + subtype per article; prior editorial; format feature fixed"},
        {"city": "jakarta", "category": "Business", "flag": "cluster 41% stay (D26)", "resolution": "type, subtype and format per article; prior editorial/business"},
        {"city": "bali", "category": "Travel", "flag": "clusters do 42% + 32% / stay 26% vs fixed editorial", "resolution": "type, subtype, format and location per article; prior editorial/city-guide; D06 + D14 attached"},
        {"city": "bali", "category": "Stranger In Paradise", "flag": "format clusters 57% medium / 43% evergreen", "resolution": "format per article; prior opinion; alternate heritage"},
        {"city": "bali", "category": "Chaine Des Rottiseurs", "flag": "cue format review 50%, event 0%", "resolution": "format per article; prior review (was event); type eat/fine-dining stays"},
        {"city": "bali", "category": "Cook and Mix", "flag": "cue type eat 93% (food vocabulary in recipes)", "resolution": "type + subtype per article; prior editorial/lifestyle; `eat` only when a restaurant is the subject"},
    ],
}

# Per-category overrides. Keys: per_article (added to the E2.0 list), type,
# subtype, format, location, facets, alternates_prepend, decisions_add,
# basis (decision ids and/or "mixed-categories"), note.
CATEGORY_RESOLUTIONS: dict[str, dict[str, dict]] = {
    "jakarta": {
        "Business": {
            "per_article": ["type", "subtype", "format"],
            "alternates_prepend": ["stay/hotel + news when a hotel, GM appointment or opening is the subject (cluster 41%)", "eat/restaurant when an F&B business is the subject"],
            "basis": ["D26", "mixed-categories"],
            "note": "editorial/business stays the prior; the classifier may switch to a venue type. Format per article between feature/news/opinion.",
        },
        "Reviews": {
            "per_article": ["type", "subtype"],
            "alternates_prepend": ["drink/wine-bar|bar + review for wine, beer and coffee pieces (cluster 23%)"],
            "basis": ["mixed-categories"],
            "note": "Format `review` stays fixed (not flagged). Type eat/restaurant is the prior.",
        },
        "Features": {
            "per_article": ["type", "subtype"],
            "alternates_prepend": ["eat/restaurant when a restaurant is the subject (cue 50%)"],
            "basis": ["mixed-categories", "D10"],
            "note": "Format `feature` stays fixed; the container rule (D10) applies when a child category is present.",
        },
        "Uncategorized": {
            "basis": ["D09"],
            "note": "No prior; every facet from content; standard confidence gate; the four page-like titles are migrated, not excluded.",
        },
        "World Traveller": {
            "basis": ["D06"],
            "note": "location `international` (geo_scope abroad): searchable, Row 3 eligible, never Row 2 or the itinerary. Children of `international` are picked per article once the 22 destination nodes are seeded.",
        },
    },
    "bali": {
        "Travel": {
            "per_article": ["type", "subtype", "format", "location"],
            "decisions_add": ["D06", "D14"],
            "alternates_prepend": ["do/* + guide for island and destination pieces (clusters 42% + 32%)", "stay/resort + review|offer for hotel pieces (cluster 26%)", "location `international` when the destination is abroad (D06); other/* for the archipelago (D14 adds the region nodes)"],
            "basis": ["mixed-categories", "D06", "D14"],
            "note": "editorial/city-guide stays the prior; the evidence split (do/stay clusters) made type per article.",
        },
        "Stranger In Paradise": {
            "per_article": ["format"],
            "alternates_prepend": ["heritage (evergreen) for the historical and cultural essays -- cluster 43%"],
            "basis": ["mixed-categories", "D24", "D03", "D08"],
            "note": "Prior stays editorial/opinion + opinion (LLM: high-confidence opinion; first-person column). D24's text listed this column under heritage -- see D24.conflicts.",
        },
        "Chaine Des Rottiseurs": {
            "format": "review",
            "per_article": ["format"],
            "alternates_prepend": ["event + event only for an announced upcoming dinner (D02 expiry applies)", "editorial/people + people for member profiles"],
            "basis": ["mixed-categories", "D08", "D02"],
            "note": "Retrospective reports on society dinners (2015-2018): the cue instrument reads 50% review, 0% event, so the prior flips to review (540-day decay; all long expired either way). Type eat/fine-dining stays.",
        },
        "Cook and Mix": {
            "per_article": ["type", "subtype"],
            "alternates_prepend": ["eat/restaurant ONLY when a restaurant is the subject -- a recipe or cocktail how-to is editorial/lifestyle even when a dish, chef or venue is named"],
            "basis": ["mixed-categories", "D08", "D05"],
            "note": "The 93% `eat` cue is food vocabulary, not a venue subject (LLM agrees: editorial/lifestyle, high confidence). Per article under the mixed-categories answer, with the classifier note above.",
        },
        "Must Watch Movies": {
            "location": "bali",
            "basis": ["D08", "D05"],
            "note": "Migrated, searchable, series_key column:must-watch-movies. Rails-excluded (follow-up #1, 2026-09-10): see rules.columns.excluded_from_rails -- series-level rule, not the quality floor. No place in the text -> site-home location fallback.",
        },
        "Music to the Ears": {
            "location": "bali",
            "basis": ["D08", "D05"],
            "note": "Migrated, searchable, series_key column:music-to-the-ears. Rails-excluded (follow-up #1, 2026-09-10): see rules.columns.excluded_from_rails -- series-level rule, not the quality floor. No place in the text -> site-home location fallback.",
        },
        "Health & Wellness": {
            "location": "bali",
            "basis": ["D08", "D05"],
            "note": "Lockdown at-home wellness column; site-home location fallback. Not rails-excluded -- follow-up #1 named only Must Watch Movies and Music to the Ears.",
        },
        "Home Life": {
            "location": "bali",
            "basis": ["D08", "D27"],
            "note": "Parent of the lockdown columns (1 post); site-home location fallback.",
        },
        "Weddings": {
            "facets": {"occasion": ["wedding"]},
            "basis": ["D22", "D01"],
            "note": "occasion `wedding` replaces `celebration` once the term is seeded (vocabulary-delta). Type/format per article; period-stamped roundups -> listing (D01).",
        },
        "Community": {
            "basis": ["D19"],
            "note": "Prior feature; topic community always. The subtype prior `news` is weak (the LLM suggested a `community` editorial subtype, which does not exist); the classifier picks among people/culture/lifestyle per article.",
        },
        "Uncategorized": {
            "basis": ["D09"],
            "note": "No prior; every facet from content; standard confidence gate; 'Purchasing NOW! Bali & TIMELESS Bali Magazines' is migrated, not excluded.",
        },
    },
}

# Cross-cutting classifier rules -- what E2.1 reads besides categories[].proposal.
RULES: dict = {
    "version": 1,
    "decided_by": DECIDED_BY,
    "decided_on": DECIDED_ON,
    "prior_resolution": {  # D10
        "decision": "D10",
        "order": ["yoast_primary", "deepest_child", "parent_container"],
        "note": "The WP category is a prior, not the answer. Take the prior from the Yoast primary category when set; otherwise from the deepest (most specific) category the post carries; a parent-only container (Lifestyle, Culture, Explore Bali, Offers, Dining, Features, ...) is a weak prior for posts that carry nothing else. Explore Bali + Opinion -> Opinion wins (D18).",
    },
    "guide_vs_listing": {  # D01
        "decision": "D01",
        "listing_when": {"period_stamp": ["a year in the title", "[Updated]", "a seasonal marker (Ramadan, Christmas, Nyepi, ...)"], "roundup": True},
        "listing": {"format": "listing", "half_life_days": 540, "series_key": "roundup:<title slug with the period stamp removed>", "rails": "one member per series_key -- the current edition only (series dedup, Section 8.A)"},
        "guide": {"format": "guide", "evergreen": True, "when": "timeless how-to or area piece with no period stamp"},
        "not_city_guide": "venue roundups filed under 'City Guides' are typed by the roundup's venue type per article, never format city-guide",
    },
    "legacy_expiry": {  # D02
        "decision": "D02",
        "offer": {"ends_at": "the validity end date extracted from the text when a phrase like 'valid until' / 'available through' exists; otherwise published_at + 90 days"},
        "event": {"ends_at": "the event end date extracted from the text when present; otherwise published_at + 30 days"},
        "expired": "stays searchable; excluded from every rail by the Section 8.A hard filter",
    },
    "print_issues": {  # D07
        "decision": "D07",
        "facets_from_category": "none",
        "series_key": "issue:<category slug>",
        "format_prior": "feature",
        "everything_else": "from content",
    },
    "columns": {  # D08
        "decision": "D08",
        "series_key": "column:<category slug>",
        "migrated": "all",
        "rails_exclusion": "none for every column except the two named in excluded_from_rails (Hansel, follow-up #1, 2026-09-10)",
        "excluded_from_rails": {
            "follow_up": 1,
            "decided_on": "2026-09-10",
            "series_keys": ["column:must-watch-movies", "column:music-to-the-ears"],
            "why_these_two": "the only two columns with no Bali subject at all (E2.0's own framing); every other column -- including Chaine Des Rottiseurs, Cook and Mix, Health & Wellness, Home Life -- is migrated with no rails exclusion.",
            "mechanism": "series-level rule",
            "mechanism_rejected_alternatives": {
                "quality_floor": "rejected -- engine.quality_scores (threshold 0.35, Section 8.A) is a generic content-quality signal uncorrelated with 'has no local subject'; a well-written entry in these two columns could score above 0.35 and slip back onto the rails, or a future well-written column with a local subject could score below 0.35 and be excluded by accident. The wrong lever for a deliberate editorial call.",
                "rails_eligible_flag": "rejected -- would need a new persisted per-category or per-article boolean nobody has built (a platform-DB column or term attribute); more schema than the decision needs.",
            },
            "mechanism_chosen_because": "series_key is already a resolved facet (D08: `column:<slug>`, unique per column) and the platform already has a hard-filter predicate shaped exactly like this one -- series dedup in `now_filters.hard` (Section 8.A). Adding one more predicate, `series_key NOT IN (:excluded_series_keys)`, alongside it needs no schema change and no scoring dependency; it is deterministic and traceable straight back to this decision.",
            "scope": "excludes these two series from every rail that recommends articles alongside other content -- Row 3 (similar/related reading) is the only such rail today (Row 1/Row 2 are place rails and never see these articles regardless). Unaffected: search, the reader's own archive/category browse, and the site-home location prior these two columns still carry.",
            "still_true": "both columns are migrated in full, stay fully searchable, and keep their series_key and site-home location prior -- only Row 3 recommendation is suppressed.",
        },
        "location_fallback": "site home when the text names no place",
    },
    "migration_scope": {  # D09 / D08
        "decisions": ["D09", "D08"],
        "excluded_categories": [],
        "uncategorized": "no prior; classify best-effort",
        "non_articles": "not excluded by the taxonomy; the five page-like titles are listed in decisions[D09].resolution.conflicts",
    },
    "confidence_gate": {
        "auto_apply_at_or_above": 0.85,
        "below": "E2.8 review queue -- never written as fact",
        "source": "PROGRESS.md E2.1 spec ('< 0.85 -> review queue'); applies to every category, including Uncategorized (D09)",
    },
    "mixed_categories": {
        "id": EVIDENCE_FLAG_POLICY["id"],
        "policy": EVIDENCE_FLAG_POLICY["answer"],
        "rule": EVIDENCE_FLAG_POLICY["rule"],
        "protects": "competitor exclusion (a fixed category-wide venue type would exclude or admit the wrong articles)",
    },
    "location": {  # D06 + the required-facet fallback
        "required": True,
        "site_home_fallback": {"jakarta": "jakarta", "bali": "bali"},
        "syndication": "Jakarta 'Bali Updates' (111) carry location bali -- the Section 3.5 syndication set for now_bali",
        "international": {
            "decision": "D06",
            "term": "location/international",
            "children": "one node per destination with >= 20 corpus mentions (22 -- see vocabulary-delta.json); a child inherits the root's attribute",
            "attribute": {"key": "geo_scope", "value": "abroad", "inherited_by_descendants": True, "default_elsewhere": "home"},
            "eligible": ["search", "row3_similar (related reading)", "reader location filter"],
            "excluded": ["row1_complementary", "row2_nearby", "itinerary builder"],
            "classifier_rule": "`international` (or a child) only when the piece is about a destination outside Indonesia; a Jakarta piece that mentions Singapore Airlines is still `jakarta`. An article about two places (Singapore vs Jakarta) carries both terms and is geo-anchored by the Indonesian one.",
            "subject_rule": "an article whose location terms are ALL under `international` hosts no Row 1 and no Row 2: both rails are returned as not applicable (rung `subject_abroad`, empty items, no fallback ladder), Row 3 unchanged. Answered by Hansel (follow-up #4, 2026-09-10, no longer inferred): a Paris feature has no local subject place, so Row 1 (complementary places) has exactly the same problem as Row 2 (nearby) -- both are suppressed the same way.",
            "candidate_rule": "any entity (place, event, article) whose location resolves to geo_scope=abroad is excluded from every geo-anchored pool: Row 1 and Row 2 places and itinerary slots. Row 3 and search never apply it.",
            "encoding": {
                "where": "a term attribute on location/international (`attrs.geo_scope = 'abroad'`), inherited by descendants -- persisted in engine.terms.attrs jsonb (the taxonomy README's proposed DDL #1; additive platform-DB migration)",
                "enforced_by": "the geo-anchored consumers, in one place each: `now_filters.hard` gains an `abroad_terms` parameter (the set of location term ids/slugs under `international`, loaded once from the platform DB like now_rails.relations_cache loads type_relations) applied as `area_term::text != ALL(:abroad_area_slugs)` for places and `NOT EXISTS (SELECT 1 FROM engine.entity_terms et WHERE et.entity_id = a.id::text AND et.term_id = ANY(:abroad_term_ids))` for articles; Row 1, Row 2 and the itinerary callers all pass it (Row 1 added by follow-up #4 -- it was previously omitted because the answer had only been inferred, not stated). `now_rails.subject` fetches the subject article's location term ids from engine.entity_terms; all-abroad -> Row 1 and Row 2 both short-circuit to `subject_abroad`.",
                "why_not_a_facet_flag": "a per-article flag duplicates information derivable from location and must be kept in sync by the classifier; the attribute lives once, on the term, and every future child (Japan, Europe, ...) inherits it.",
                "why_not_rails_only_code": "three consumers now (Row 1 and Row 2 today, the E5 itinerary builder later) and a growing node set; a hardcoded slug list in each rail drifts. The rails still own the enforcement -- the attribute only tells them which nodes are abroad.",
                "prerequisite": "`public.articles` has no location column; article location lives only in engine.entity_terms (empty today). E2.1 must write the location facet there (or E2.1's ticket adds a denormalised `articles.primary_location`); without one of the two, the subject rule cannot be evaluated for either rail (PROGRESS.md F82).",
            },
        },
        "reparenting": {
            "decision": "D14 (follow-up #4, 2026-09-10)",
            "status": "approved by Hansel -- NOT applied by this package",
            "answer": "Indonesian cities proposed or already seeded flat under the `other` root are re-parented under their island region node (java, sumatra, sulawesi, kalimantan, nusa-tenggara, maluku -- the region nodes this pack's vocabulary-delta adds under `other`, see vocabulary_delta.py). Change is `parent_id` only: no slug, label, alias, geo or attribute changes.",
            "examples": "solo/malang/surabaya/semarang -> java; medan/palembang/padang/lampung/cirebon -> sumatra; makassar/toraja -> sulawesi; manado -> sulawesi; aceh -> sumatra; riau-islands -> sumatra. lombok, komodo and sumba stay their own leaves alongside nusa-tenggara per vocabulary_delta.py's existing note -- unaffected by this answer.",
            "owner": "the seed ticket applying the location vocabulary delta to engine/packages/taxonomy/seed/ this same wave, in parallel with this pack -- NOT this package (out of scope: 'Do NOT touch engine/packages/taxonomy/seed/'). This record exists so that agent's delta and this pack's vocabulary-delta.json agree it is approved and stop treating it as an open question.",
            "was": "vocabulary_delta.py previously carried this as an open question on the java/Sumatra/etc. region-node notes; those notes now say 'approved' instead.",
        },
    },
}
