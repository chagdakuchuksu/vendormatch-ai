# VendorMatch AI — M0: Architecture & Data Model

Status: **approved** (with revisions below). M1 implements the deterministic scoring engine.

Revisions after review:
1. Importance only supplies the default weight; an explicit weight replaces it. Importance's only
   other effect is the severity of a *failed hard* requirement (§3.2, §3.7).
2. Flexible quadratic curve kept, `τ` default 25 %, configurable per criterion (§3.3).
3. Auto-generated technology criteria are **Critical + Hard** (§2.3).
4. Failed hard requirements stay visible, score 0, apply the multiplier, and carry evidence (§3.6).
5. Semantic thresholds are provisional calibration constants (§3.5).
6. SQLite kept; Cloud Run storage is ephemeral (§4).

Implementation note (M1): the materialization logic described in §2.3 lives in
`app/services/criteria_builder.py` (pure, no DB); the scorers in `app/services/scoring/`.

VendorMatch AI is a decision-support tool. It produces transparent, explainable
compatibility scores. It never declares a vendor "the best" and never removes a
vendor from the comparison.

---

## 1. Folder structure

```
vendormatch-ai/
├── app/
│   ├── main.py                  # FastAPI app factory, router registration, static mount
│   ├── config.py                # Settings + ScoringConfig (every scoring constant lives here)
│   ├── errors.py                # Domain exceptions + JSON error handlers
│   ├── api/
│   │   ├── deps.py              # DI: db connection, embedder, services
│   │   ├── projects.py          # /api/projects
│   │   ├── vendors.py           # /api/projects/{id}/vendors, /api/vendors/{id}
│   │   ├── analysis.py          # /api/projects/{id}/analysis, /comparison
│   │   └── meta.py              # /api/health, /api/scoring-model, /api/demo
│   ├── schemas/
│   │   ├── enums.py             # Importance, RequirementType, Flexibility, CriterionKind, ...
│   │   ├── criterion.py         # CriterionIn, Criterion
│   │   ├── project.py           # ProjectCreate, ProjectUpdate, Project
│   │   ├── vendor.py            # VendorCreate, VendorUpdate, Vendor
│   │   └── analysis.py          # CriterionResult, VendorAnalysis, ProjectAnalysis, ComparisonRow
│   ├── services/
│   │   ├── project_service.py   # create/update + criteria materialization & weight normalization
│   │   ├── vendor_service.py
│   │   ├── analysis_service.py  # orchestrates scorers → VendorAnalysis
│   │   ├── demo_service.py      # loads examples/ into the DB
│   │   ├── scoring/
│   │   │   ├── numeric.py       # budget, duration, experience (pure functions)
│   │   │   ├── technology.py    # deterministic technology matching
│   │   │   ├── text.py          # semantic criterion scoring (uses semantic/)
│   │   │   └── aggregate.py     # weighted sum, hard-failure penalty, counts
│   │   └── semantic/
│   │       ├── embedder.py      # Embedder protocol, SentenceTransformerEmbedder (lazy, cached)
│   │       └── matcher.py       # chunking, cosine similarity, best-evidence selection
│   ├── data/
│   │   ├── database.py          # sqlite3 connection, schema creation
│   │   └── repositories.py      # ProjectRepository, VendorRepository
│   └── utils/
│       ├── weights.py           # normalize_weights()
│       ├── units.py             # duration unit conversion
│       └── text.py              # tech-name normalization, sentence splitting, money formatting
├── examples/
│   ├── demo_project.json
│   └── demo_vendors.json        # 3 fictional vendors
├── static/                      # (M5) HTML/CSS/vanilla JS
├── tests/
│   ├── conftest.py              # tmp SQLite, FakeEmbedder, TestClient
│   ├── unit/ ...
│   ├── integration/ ...
│   └── model/ ...               # real MiniLM tests (marker: model)
├── docs/
├── Dockerfile
├── requirements.txt / requirements-dev.txt
├── pyproject.toml               # pytest config, markers, ruff
└── .github/workflows/ci.yml
```

Design rules:
- `services/scoring/*` are **pure functions** (no DB, no I/O). Inputs: a criterion, a vendor,
  a config. Output: a `CriterionResult`. This is what makes scoring deterministic and easy to test.
- The semantic model sits behind an `Embedder` protocol, so tests can inject a fake.
- Persistence uses stdlib `sqlite3` + JSON columns (no ORM) — enough for an MVP.

---

## 2. Pydantic models

### 2.1 Enums (`schemas/enums.py`)

| Enum | Values |
|---|---|
| `Importance` | `critical`, `high`, `medium`, `low` |
| `RequirementType` | `hard`, `soft` |
| `Flexibility` | `strict`, `flexible` (numeric kinds only) |
| `CriterionKind` | `budget`, `duration`, `experience`, `technology`, `text` |
| `DurationUnit` | `weeks`, `months` |
| `CriterionStatus` | `pass`, `warning`, `fail`, `missing` |
| `CriterionSource` | `user`, `auto` |

`CriterionKind` decides **how** a criterion is evaluated:

| Kind | Evaluated against | Method |
|---|---|---|
| `budget` | `project.budget` vs `vendor.proposed_budget` | deterministic, "max" constraint |
| `duration` | `project.max_duration` vs `vendor.proposed_duration` | deterministic, "max" constraint |
| `experience` | `criterion.min_value` vs `vendor.years_experience` | deterministic, "min" constraint |
| `technology` | `criterion.technology` vs `vendor.technologies` | deterministic, normalized name match |
| `text` | `criterion.name + description` vs proposal text + previous projects | semantic similarity |

Semantic similarity is used **only** for `text` criteria. It can never change a numeric or
technology result.

### 2.2 Criterion (`schemas/criterion.py`)

```python
class CriterionIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    kind: CriterionKind
    description: str | None = Field(None, max_length=1000)   # required for kind=text
    importance: Importance = Importance.medium
    requirement_type: RequirementType = RequirementType.soft
    flexibility: Flexibility | None = None    # required for budget/duration/experience, forbidden otherwise
    tolerance: float | None = Field(None, gt=0, le=1)  # flexible only; default from config (0.25)
    weight: float | None = Field(None, ge=0)  # None → default weight of the importance level
    min_value: float | None = Field(None, ge=0)  # experience only (years)
    technology: str | None = None             # technology only

    # model_validator enforces the kind-specific field rules above

class Criterion(CriterionIn):
    id: str                       # slug, unique within the project
    source: CriterionSource       # user-defined or auto-generated from project fields
    weight_source: WeightSource   # "explicit" or "importance_default"
    effective_weight: float       # explicit weight, or the importance default
    normalized_weight: float      # 0..1, sums to 1 across the project
```

### 2.3 Project (`schemas/project.py`)

```python
class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str = Field("", max_length=5000)
    budget: Decimal | None = Field(None, gt=0)
    currency: str = Field("EUR", pattern=r"^[A-Z]{3}$")
    max_duration: float | None = Field(None, gt=0)
    duration_unit: DurationUnit = DurationUnit.months
    required_technologies: list[str] = []
    criteria: list[CriterionIn] = []

class ProjectUpdate(ProjectCreate): ...      # full replace (PUT), keeps MVP simple

class Project(ProjectCreate):
    id: int
    criteria: list[Criterion]                # materialized, complete list
    is_demo: bool = False
    created_at: datetime
```

**Criteria materialization** (done once in `project_service`, at create/update — the stored
project always contains the full, explicit criteria list, so there is no hidden runtime logic):

1. User criteria are kept as-is (`source=user`).
2. If `budget` is set and no `budget` criterion exists → add one with defaults
   `High / Soft / Flexible` (`source=auto`).
3. If `max_duration` is set and no `duration` criterion exists → add one with defaults
   `High / Hard / Strict`.
4. For each `required_technologies` entry without a matching `technology` criterion → add one
   with defaults `Critical / Hard` (weight = Critical default, 4). Project-level required
   technologies are explicitly required by the company, so they are hard by default. Users can
   change them afterwards like any other criterion (or define their own criterion for that
   technology up front, which replaces the auto one).
5. Validation: a `budget` criterion without `project.budget` (or `duration` without
   `max_duration`) → 422. Duplicate technology criteria → 422.
6. Weights are normalized (section 3.2).

Auto-generated criteria are visible and editable in the UI and API response, labelled `auto`.

### 2.4 Vendor (`schemas/vendor.py`)

```python
class VendorCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    proposed_budget: Decimal | None = Field(None, gt=0)   # in the project's currency
    proposed_duration: float | None = Field(None, gt=0)
    duration_unit: DurationUnit = DurationUnit.months
    years_experience: float | None = Field(None, ge=0)
    technologies: list[str] = []
    proposal_text: str = Field("", max_length=10000)
    previous_projects: list[str] = []          # short free-text descriptions

class Vendor(VendorCreate):
    id: int
    project_id: int
    is_demo: bool = False
    created_at: datetime
```

No currency conversion in the MVP: vendor budgets are assumed to be in the project currency.

### 2.5 Analysis output (`schemas/analysis.py`)

```python
class Deviation(BaseModel):
    absolute: float          # e.g. 5000.0 or 2.0
    relative: float          # e.g. 0.10 (10 %)
    unit: str                # "EUR", "months", "years"
    direction: Literal["over", "under", "none"]

class SemanticEvidence(BaseModel):
    similarity: float        # raw cosine similarity
    matched_text: str        # best-matching sentence from the proposal
    strength: Literal["strong", "partial", "none"]

class CriterionResult(BaseModel):
    criterion_id: str
    name: str
    kind: CriterionKind
    requirement_type: RequirementType
    importance: Importance
    flexibility: Flexibility | None
    normalized_weight: float
    score: float                       # 0..1
    contribution: float                # normalized_weight * score * 100 (points)
    status: CriterionStatus
    required_value: str                # "≤ €50,000", "≤ 6 months", "React Native"
    vendor_value: str                  # "€55,000", "8 months", "not listed"
    deviation: Deviation | None
    evidence: SemanticEvidence | None
    hard_failure: bool
    penalty_factor: float | None       # multiplier applied, only when hard_failure
    summary: str                       # badge text: "€5,000 over budget"
    explanation: str                   # "€55,000 is €5,000 (10%) above the preferred maximum budget ..."

class RequirementCounts(BaseModel):
    hard_passed: int; hard_warning: int; hard_failed: int
    soft_passed: int; soft_warning: int; soft_failed: int

class VendorAnalysis(BaseModel):
    vendor_id: int
    vendor_name: str
    overall_score: float               # 0..100, 1 decimal
    base_score: float                  # before hard-failure penalty
    hard_penalty_factor: float         # 1.0 if no hard failures
    hard_requirements_met: bool
    status_label: str                  # "All hard requirements met" / "Hard requirement failed: Duration"
    counts: RequirementCounts
    criteria: list[CriterionResult]
    missing_requirements: list[str]    # failed/missing criteria names
    concerns: list[str]                # warnings + informational flags (e.g. unusually low bid)
    budget_deviation: Deviation | None
    duration_deviation: Deviation | None
    technology_coverage: float | None  # share of technology criteria matched

class ProjectAnalysis(BaseModel):
    project_id: int
    scoring_version: str               # e.g. "1.0" — bump when constants change
    generated_at: datetime
    vendors: list[VendorAnalysis]      # ordered by overall_score, ties by name
    disclaimer: str                    # "Decision support only. Final selection is yours."

class ComparisonRow(BaseModel):
    vendor_id: int
    vendor_name: str
    overall_score: float
    hard_requirements: str             # "100%" or "Failed (1)"
    budget: str                        # "€55K"
    duration: str                      # "5 mo"
    technology_coverage: str           # "67%"
    status: Literal["pass", "warning", "fail"]
```

---

## 3. Scoring model

All constants below live in `ScoringConfig` and are returned by `GET /api/scoring-model`.

### 3.1 Notation

- Criteria `i = 1..n`, raw weight `w_i ≥ 0`, normalized weight `W_i`.
- Criterion score `s_i ∈ [0, 1]`.
- `H_f` = set of **hard** criteria with status `fail` or `missing`.

### 3.2 Weights

Default raw weight by importance (used when `weight` is omitted):

| Importance | Default weight | Hard-failure factor `p` |
|---|---:|---:|
| Critical | 4 | 0.50 |
| High | 3 | 0.60 |
| Medium | 2 | 0.70 |
| Low | 1 | 0.80 |

```
w_i = weight_i                  if the user provided a weight      (weight_source = explicit)
    = default_weight(importance_i)  otherwise                       (weight_source = importance_default)
W_i = w_i / Σ_j w_j
```

**Importance vs. weight — no double counting.** Importance is used in exactly two places:

1. As the *default* weight when no weight is given. If the user gives a weight, importance has
   **no** effect on the criterion's points. (Two soft criteria with equal weights cost the same
   points when they fail, whatever their importance.)
2. As the severity of a **failed hard** requirement (factor `p`, §3.6). It never multiplies the
   score of a passing criterion or of a soft criterion.

- `w_i < 0` → rejected by validation (422).
- `w_i = 0` → allowed. The criterion is still evaluated and displayed, but contributes no
  points. **A zero-weight hard criterion still triggers the hard-failure penalty** — "hard"
  means "must be satisfied", independent of weight.
- `Σ w_j = 0` (or no criteria) → 422 "at least one criterion must have a positive weight".
- Any scale works: weights `[40, 30, 30]` and `[4, 3, 3]` give identical results.

### 3.3 Numeric criteria (budget, duration, experience)

Relative deviation in the "bad" direction:

```
max-constraint (budget, duration):  d = max(0, (v − T) / T)
min-constraint (experience):        d = max(0, (T − v) / T)
```

`T` = target, `v` = vendor value.

**Duration units (scoring v1.1).** Same-unit durations are compared directly. Different units
are normalized through days with exact rational arithmetic (`fractions.Fraction`, no rounding,
no tolerance) and then expressed in the project's unit:

| Unit | Days |
|---|---|
| 1 week | 7 |
| 1 month | 364 / 12 = 30⅓ (1/12 of a 52-week planning year) |

So 3 months = 13 weeks = 91 days, 6 months = 26 weeks = 182 days, 12 months = 52 weeks = 364
days — exactly. A real calendar month averages ≈ 30.44 days; the planning-year convention is
used because timelines are planned in whole weeks, and a fixed factor (v1.0 used 4.345
weeks/month) made 6 months "26.07 weeks" and failed a strict 26-week deadline by 0.07 weeks.
Genuine differences remain: 3 months (91 days) is still 1 week over a strict 12-week limit
(84 days). Implementation: `app/utils/units.py`.

Score:

```
d = 0                     → s = 1                          status = pass
Strict,   d > 0           → s = 0                          status = fail
Flexible, 0 < d < τ       → s = 1 − (d / τ)²               status = warning
Flexible, d ≥ τ           → s = 0                          status = fail
vendor value missing      → s = 0                          status = missing
```

`τ` (tolerance) defaults to **0.25** (a 25 % overshoot reaches zero), overridable per criterion.
The quadratic curve makes small deviations cheap and large ones progressively expensive:

| Overshoot `d` | 0 % | 5 % | 10 % | 15 % | 20 % | ≥ 25 % |
|---|---:|---:|---:|---:|---:|---:|
| Score `s` (τ = 0.25) | 1.00 | 0.96 | 0.84 | 0.64 | 0.36 | 0 |
| Status | pass | warning | warning | warning | warning | fail |
| Example: budget €50,000, bid | €50,000 | €52,500 | €55,000 | €57,500 | €60,000 | ≥ €62,500 |

Each extra 5 % of overshoot costs more than the previous 5 % (losses 0.04, 0.12, 0.20, 0.28, ...).

Other tolerances (configurable per criterion via `tolerance`):

| `d` | τ = 0.10 | τ = 0.25 | τ = 0.50 |
|---|---:|---:|---:|
| 5 % | 0.75 | 0.96 | 0.99 |
| 10 % | 0 (fail) | 0.84 | 0.96 |
| 25 % | 0 (fail) | 0 (fail) | 0.75 |

Strict example: max duration 6 months, vendor 8 months → `d = 0.33 > 0` → `s = 0`, fail
("2 months over the strict deadline").

A flexible **hard** criterion fails (and triggers the hard penalty) only once `d ≥ τ`; inside the
tolerance zone it is a warning.

Being under budget / faster gives no bonus (s = 1). A bid more than **40 %** below the budget
adds an informational concern ("unusually low bid — verify scope") with no score effect.

### 3.4 Technology criteria

Names are normalized (lowercase, strip spaces/punctuation, small documented alias table:
`postgres→postgresql`, `node→nodejs`, `js→javascript`, ...). Match in `vendor.technologies`
→ `s = 1, pass`; otherwise `s = 0, fail`. Fully deterministic — no semantic matching.

### 3.5 Text criteria (semantic)

1. Requirement text = `description` (M2 decision: the name is a short label and would only
   duplicate the description).
2. Evidence chunks = proposal text split into sentences + each previous-project entry.
3. Embed with `all-MiniLM-L6-v2` (locally), cosine similarity, take the best chunk:
   `σ = max_k cos(req, chunk_k)`.
4. Map to a score with a linear ramp between two thresholds:

```
s = clamp((σ − L) / (U − L), 0, 1)        L = 0.30, U = 0.60 (initial values)

σ ≥ U        → strength "strong",  status pass
L < σ < U    → strength "partial", status warning
σ ≤ L        → strength "none",    status fail   (listed in missing_requirements)
```

The best-matching sentence is returned as `evidence.matched_text`.

**`L = 0.30` and `U = 0.60` are provisional calibration constants**, chosen as reasonable
starting points for `all-MiniLM-L6-v2` cosine similarity. They are **not** scientifically
validated thresholds. M2 adds calibration tests on representative example pairs (e.g.
"e-commerce experience" ↔ "six online retail platforms", "payment integration" ↔ "Stripe,
PayPal and Adyen", plus unrelated pairs) and documents the values that come out of them.
→ Done: see [M2-semantic-matching.md](M2-semantic-matching.md). Thresholds kept unchanged.

### 3.6 Aggregation

```
base_score    = 100 · Σ_i W_i · s_i
penalty       = Π_{i ∈ H_f} p(importance_i)          (= 1 if no hard failures)
overall_score = base_score · penalty
```

A failed hard criterion (status `fail` or `missing`):

a) scores 0 for that criterion,
b) multiplies the overall score by its documented factor (Critical 0.5, High 0.6, Medium 0.7,
   Low 0.8 — compounding, e.g. two Critical failures → ×0.25; applies even at weight 0),
c) is reported as a failed requirement with evidence: `hard_failure = true`, `penalty_factor`,
   `required_value` vs `vendor_value`, the `deviation`, a `summary` and a full `explanation`,
   plus `status_label = "Hard requirement failed: <names>"` on the vendor.

Vendors are **never removed or hidden**: every vendor keeps every criterion result and appears
in the comparison.

### 3.7 How the four dimensions interact

| Dimension | Controls |
|---|---|
| **Weight** | How many points a criterion is worth (its share of the 100). |
| **Importance** | Default weight *only* when no weight is given; and the severity `p` of a *failed hard* criterion. Never an extra multiplier otherwise. |
| **Hard / Soft** | Whether failing triggers the multiplicative penalty + "hard requirement failed" flag. Soft failures only lose their points. |
| **Strict / Flexible** | Numeric only: whether any deviation is a failure (strict) or there is a graded tolerance zone (flexible). Hard + Flexible fails only beyond the tolerance. |

### 3.8 Worked example (spec example)

Criteria: Duration (Critical, Hard, Strict, w=4), Budget (High, Soft, Flexible, w=3),
React Native (Critical, Hard, w=4), E-commerce experience (High, Soft, text, w=3),
Experience ≥ 5 yrs (Medium, Soft, Flexible, w=2), Node.js (auto, Critical, Hard, w=4),
PostgreSQL (auto, Critical, Hard, w=4). Σw = 24.

**Vendor A** — €55K, 5 months, 8 years, all techs, strong e-commerce match:
budget d = 0.10 → s = 0.84, loses 3/24 · 0.16 · 100 = 2.0 pts. Everything else passes.
Overall = **98.0**, all hard requirements met → over the flexible budget but clearly competitive.

**Vendor B** — €40K, 8 months, 10 years, all techs, strong e-commerce match:
duration d = 0.33, Strict → s = 0, hard failure. base = 100 − 4/24 · 100 = 83.3;
penalty = 0.50 (Critical) → overall = **41.7**, flagged
"Hard requirement failed: Duration" with summary "2 months over the strict deadline".

Both are golden tests in `tests/unit/test_engine.py`.

---

## 4. API endpoints

All JSON under `/api`. Errors use one shape: `{"error": {"code", "message", "details"}}`.

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/health` | Liveness (Cloud Run) |
| GET | `/api/scoring-model` | All scoring constants + scoring version (transparency) |
| POST | `/api/demo` | Load fictional demo project + 3 vendors → `{project_id}` |
| POST | `/api/projects` | Create project (criteria materialized, weights normalized) |
| GET | `/api/projects` | List projects (with vendor counts) |
| GET | `/api/projects/{id}` | Get project with full criteria |
| PUT | `/api/projects/{id}` | Replace project |
| DELETE | `/api/projects/{id}` | Delete project and its vendors |
| POST | `/api/projects/{id}/vendors` | Add vendor |
| GET | `/api/projects/{id}/vendors` | List vendors |
| GET | `/api/vendors/{id}` | Get vendor |
| PUT | `/api/vendors/{id}` | Replace vendor |
| DELETE | `/api/vendors/{id}` | Delete vendor |
| GET | `/api/projects/{id}/analysis` | Full `ProjectAnalysis` (computed on demand) |
| GET | `/api/projects/{id}/comparison` | `list[ComparisonRow]` |

Analysis is **computed on demand, not persisted**: it is deterministic and cheap (embeddings
are cached in memory per text), so persisting results would only add staleness problems.
The "Analyze" button simply calls the analysis endpoint.

**Storage note:** SQLite is kept for the MVP. On Google Cloud Run the container filesystem is
per-instance and ephemeral, so demo data **may reset whenever an instance restarts or scales**.
This is acceptable for a public demo (the demo reloads in one click) and will be stated in the
README and the UI footer.

---

## 5. Test strategy

Framework: pytest. No external APIs, no API keys.

**Layers**

1. **Unit (fast, pure)** — scoring functions with hand-built criteria/vendors. No DB, no model.
2. **Semantic unit** — `matcher.py` with a `FakeEmbedder` (deterministic vectors) to test
   chunking, best-evidence selection, threshold mapping.
3. **Integration** — FastAPI `TestClient`, temp SQLite file, `FakeEmbedder` injected via
   dependency override.
4. **Model tests** (`@pytest.mark.model`) — real `all-MiniLM-L6-v2`, run locally and in CI
   with the Hugging Face cache stored via `actions/cache`. Model weights are downloaded once;
   no inference ever leaves the machine. Skipped automatically if the model is unavailable
   offline.

**Coverage map**

| Requirement | File |
|---|---|
| Budget scoring, flexible deviation, vendor over budget, missing budget | `unit/test_numeric_scoring.py` |
| Duration scoring, strict violation, missing duration, unit conversion | `unit/test_numeric_scoring.py` |
| Experience min-constraint | `unit/test_numeric_scoring.py` |
| Technology matching + normalization/aliases | `unit/test_technology.py` |
| Weight normalization, zero weight, all-zero weights, negative weight | `unit/test_weights.py` |
| Hard failure, soft failure, multiple hard failures, all satisfied, overall score | `unit/test_aggregate.py`, `unit/test_engine.py` |
| Criteria materialization & validation, importance vs. weight | `unit/test_criteria_builder.py` |
| Semantic matching, no semantic match, missing requirements | `unit/test_semantic_matcher.py` |
| Real-model calibration (e-commerce ↔ online retail, payments ↔ Stripe, unrelated ↔ none) | `model/test_semantic_model.py` |
| CRUD + error shapes | `integration/test_api_projects.py`, `test_api_vendors.py` |
| Multiple vendor comparison, ordering, comparison rows | `integration/test_api_analysis.py` |
| Demo data loads, validates, and produces expected outcomes | `integration/test_demo.py` |

The worked example in §3.8 becomes a golden test (exact expected scores).

---

## 6. Demo data plan (`examples/`)

Project: "ShopNest — E-commerce Mobile App (fictional)", €50,000 flexible budget, 6 months
strict, React Native (Critical, Hard), Node.js, PostgreSQL, e-commerce experience (text),
payment integration experience (text), ≥ 5 years experience.

| Vendor (all fictional) | Budget | Duration | Years | Tech | Demonstrates |
|---|---|---|---|---|---|
| Harborline Software | €55K | 5 mo | 8 | RN, Node, Postgres | Over flexible budget, still top-scoring; "online retail platforms" phrasing → semantic e-commerce match |
| Kestrel Mobile Labs | €40K | 8 mo | 10 | RN, Node, MongoDB | Cheapest, but strict-duration hard failure |
| Quillstone Digital | €46K | 6 mo | 4 | RN, Node, MySQL | Passes hard reqs; partial tech coverage, slightly short on experience, weaker semantic match |

Every name and record is marked `"is_demo": true` and labelled "Fictional" in the UI.

---

## 7. Proposed milestones

- **M1** — Schemas, config, pure scoring engine (numeric, technology, aggregate, weights) + unit tests.
- **M2** — Semantic matcher, embedder abstraction, calibration tests.
- **M3** — SQLite persistence, services, CRUD API + integration tests.
- **M4** — Analysis/comparison endpoints, demo data, demo tests.
- **M5** — Frontend (Dashboard, Projects, Vendors, Analysis, Comparison, Try Demo).
- **M6** — Dockerfile (model baked into image), GitHub Actions CI, Cloud Run deploy notes, README.
