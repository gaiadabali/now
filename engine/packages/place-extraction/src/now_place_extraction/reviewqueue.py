"""File-based review queue for uncertain place-merge decisions.

WHY NOT `public.classification_reviews` (E2.8's queue, which this ticket's
own brief pointed at): read live before writing a line of pipeline code --
`engine/packages/cms/src/collections/ClassificationReviews.ts` and
`reviewQueueHooks.ts`. Three hard mismatches, not a style preference:

  1. `facet_key` is a Postgres ENUM with exactly four values -- `type`,
     `subtype`, `format`, `location` (verified live:
     `enum_classification_reviews_facet_key`). "Is candidate A the same
     venue as candidate B" has no facet to be. Writing a fifth value is a
     schema change to a table E2.1 is concurrently writing to right now.
  2. The collection's `entity` field is a SINGLE polymorphic relationship
     (one article-or-place). A merge decision is inherently about a PAIR
     of places; there is no second-entity field to hold the other side.
  3. `afterChange` (`makeApplyClassificationDecision`) writes `finalValue`
     onto ONE scalar field of ONE entity the moment `reviewState` leaves
     `pending`. There is no write-back semantic here that means "merge
     place B into place A" -- an editor clicking the existing "accept"
     affordance on a shoehorned row would silently write a place NAME
     into some other entity's `type`/`subtype`/`format`/`location` field.

Reusing it as-is would either fail at the database (ENUM constraint) or
silently corrupt an unrelated field the day an editor clicked "accept" --
worse than "inventing a second mechanism". This instead follows the
OTHER review-queue convention already live in this exact repo -- E2.5's
`<city>/content/extracted/geocoded_places_review_queue.jsonl`
(file-based, one JSON object per line, human-reviewable, diffable in git)
-- for the same "uncertain, don't auto-apply" shape. Flagged in the
final report as a contradiction to resolve with an architect/senior-db
decision (a real second entity-relationship field + a fifth ENUM value,
or a dedicated `place-merge-reviews` collection) rather than silently
picked around.
"""

from __future__ import annotations

import json
from pathlib import Path


def write_review_queue(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
