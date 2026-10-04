# M4 — Demo scenario, analysis explainability and comparison

## Demo scenario (`examples/`, all fictional)

**E-commerce Mobile Application (fictional demo)** — €50,000 preferred budget, 6-month strict deadline.

| Criterion | Kind | Importance | Type | Weight (of 25) | Max points |
|---|---|---|---|--:|--:|
| Duration ≤ 6 months | duration | Critical | Hard, Strict | 4 | 16 |
| Budget ≤ €50,000 | budget | High | Soft, Flexible (τ 25 %) | 3 | 12 |
| React Native | technology | Critical | Hard | 4 | 16 |
| Node.js | technology | Critical | Hard | 4 | 16 |
| PostgreSQL | technology | High | Soft | 3 | 12 |
| E-commerce experience | text (semantic) | High | Soft | 3 | 12 |
| Payment integration | text (semantic) | Medium | Soft | 2 | 8 |
| Company experience ≥ 5 years | experience | Medium | Soft, Flexible | 2 | 8 |

Vendors were designed as profiles (data only; no target scores). The scoring engine decides:

| Vendor (fictional) | Profile | Key data |
|---|---|---|
| Harborline Software | strong but slightly expensive | €54,500, 5 months, 9 years, full tech stack, direct e-commerce + payment references |
| Kestrel Mobile Labs | cheap but problematic | €38,000, **8 months**, 7 years, full tech stack, relevant references |
| Quillstone Digital | balanced | €47,000, 6 months, 4 years, **MySQL instead of PostgreSQL**, limited e-commerce references |

Proposal wording was written to be realistic for each profile and checked against MiniLM; the
semantic thresholds (L = 0.30, U = 0.60) were not changed.

## Explainability additions

- Per criterion: `max_points`, `contribution`, `points_lost` (in addition to requirement, vendor
  value, score, status, weight, deviation, evidence, summary, explanation).
- Per vendor: `penalty_points`, `score_explanation` (base × multiplier = overall),
  `compatibility_label`, neutral `summary`, `major_concerns` (hard failures → unmet soft criteria →
  warnings → informational notes).

### Neutral labels (presentation only — never change a score)

| Condition | Label |
|---|---|
| any hard requirement failed | Hard requirement failed |
| overall ≥ 85 | Strong compatibility |
| overall ≥ 65 | Mostly compatible with some concerns |
| otherwise | Requires review |

Thresholds: `ScoringConfig.label_strong_min` / `label_mostly_min`. No text recommends, selects or
ranks a vendor as "best"; tests check for words such as *choose, recommend, best, winner, select*.

## Comparison payload (`GET /api/projects/{id}/comparison`)

- `criteria`: column headers (name, kind, importance, type, flexibility, required value, weight,
  max points).
- `rows[]` (ordered by score; `ordering_note` states the order is a sorting aid, not a decision):
  overall/base score, multiplier, label, summary, status; hard requirements passed / failed /
  total and names; budget, duration, technology and semantic values + statuses + summaries;
  missing technologies; major concerns; `cells` = per-criterion status, score, contribution,
  vendor value and summary for a full criterion × vendor matrix.

Group status rule (technology / semantic / row): `fail` if a hard criterion in the group failed,
`warning` if any criterion in the group is not fully met, otherwise `pass`.

## Known semantic limitation visible in the demo

Kestrel's "mobile storefronts and checkout flows for several online shops" scores only 0.37 for
e-commerce experience, below Quillstone's "small web shop for a local clothing boutique" (0.44),
although a human would rate Kestrel's evidence higher. This is MiniLM behaviour, not tuned away;
the evidence sentences are shown verbatim so a reviewer can judge them.
