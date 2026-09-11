# E2.6 -- Quality score report

Articles scored: **4772**

## Weighting

| component | weight |
|---|---|
| length | 0.3 |
| structure | 0.2 |
| media | 0.2 |
| yoast | 0.2 |
| author | 0.1 |

See `now_quality/scoring.py` module docstring for the justification of each weight.

## Score distribution

- min: 0.15
- p25: 0.4775
- median: 0.5841
- p75: 0.6892
- max: 1.0
- below floor (0.35): **229** / 4772

## Sub-500-char stubs -- must fall below the floor (0.35)

| id | title | chars | score | below floor? |
|---|---|---|---|---|
| 3379 | Order Form - NOW! Magazines | 0 | 0.15 | ✅ |
| 4408 | Our New Column – Share Your Thoughts With Jakarta! | 0 | 0.15 | ✅ |
| 4443 | Our Latest Magazine is Out Now! | 0 | 0.15 | ✅ |
| 467 | Jakarta in a Decade | 3 | 0.15 | ✅ |
| 1819 | The Charm and Beauty of Ballet | 153 | 0.15 | ✅ |
| 360 | SKAL 18 August 2019 at Le Meridien Jakarta | 236 | 0.15 | ✅ |
| 358 | SWISS NATIONAL DAY | 261 | 0.15 | ✅ |
| 165 | King's Day | 267 | 0.15 | ✅ |
| 166 | SKAL Gathering | 268 | 0.15 | ✅ |
| 842 | Avoiding The Old Normal | 271 | 0.15 | ✅ |
| 787 | The Philosophy of Crises | 273 | 0.15 | ✅ |
| 1781 | The Spirit of Independence | 329 | 0.15 | ✅ |
| 817 | The Philosophy of Crises - Part Two | 337 | 0.15 | ✅ |
| 1101 | NOW! Jakarta Photo Contest | 390 | 0.15 | ✅ |
| 159 | Bohemian Garden Dinner | 396 | 0.15 | ✅ |
| 825 | #CookingFromHome with Chef Adrian Aditya | 420 | 0.15 | ✅ |
| 816 | #CookingFromHome with Chef Vindex Tengker | 434 | 0.15 | ✅ |
| 2440 | Go on Adventure with Iceland Vodka | 461 | 0.15 | ✅ |
| 748 | COVID-19 and the Ethics of Tourism | 463 | 0.15 | ✅ |

## Popularity prior

- head cutoff: top **300** articles by `wpb_post_views_count`
- views floor to be 'in head': **2049**
- everything outside the head: `prior_score = 0.0`, `discarded_as_bot_noise: true`
- see `now_quality/popularity.py` module docstring for the full percentile table and justification
