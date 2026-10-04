# VendorMatch AI

**AI-powered decision support for evaluating software development vendors.**
Score vendor proposals against your own requirements — budget, deadline, experience and written
requirements — and see exactly why each vendor scored what it did.

**Live demo:** [vendormatch-ai-203982728145.europe-west1.run.app](https://vendormatch-ai-203982728145.europe-west1.run.app) &nbsp;·&nbsp; **API docs:** [/docs](https://vendormatch-ai-203982728145.europe-west1.run.app/docs)

> All demo companies and data are fictional. VendorMatch AI supports a decision; it never picks a vendor.

---

## Try it in 30 seconds

1. Open the live demo and click **Try Demo** (no account, no data entry) — or **Create your own project**
   and enter your budget, deadline, minimum experience and written requirements (each with an importance),
   then add the vendor offers you received.
2. A fictional *E-commerce Mobile Application* loads with 8 requirements and 3 vendor proposals.
3. Compare the vendors side by side, then open any vendor to see every point earned or lost.

| Vendor (fictional) | Profile | Result |
|---|---|---|
| Harborline Software | Strong, ~9 % over a *flexible* budget | **97.2** · Strong compatibility |
| Quillstone Digital | On budget and time; MySQL instead of preferred PostgreSQL, less experience | **71.2** · Mostly compatible with some concerns |
| Kestrel Mobile Labs | Cheapest, but misses the *strict* 6-month deadline | **35.1** · Hard requirement failed (70.3 × 0.5) |


## Main features

- **Try Demo** — one click loads a fictional e-commerce project with three fictional vendor offers.
- **Your own projects** — a form for budget (with currency), deadline (months or weeks), minimum
  company experience and written requirements, each with an importance and an optional manual weight.
- **Vendor offers** — add, edit and delete offers: price, duration, years in business, proposal text
  and previous projects.
- **Comparison** — one row per vendor with overall score, a neutral assessment label, hard
  requirements, budget, duration, technology and text-evidence status, and the main concerns, plus a
  points-by-criterion matrix.
- **Vendor analysis** — the score formula (base score × hard-failure multiplier = overall), every
  criterion's points earned and lost, and the quoted evidence sentence for written requirements.
- **REST API** — every feature is available through FastAPI with OpenAPI docs at `/docs`; the API also
  supports technology requirements and hard/strict limits (used by the demo).

## Why it is different

- **Transparent, not a black box** — every criterion shows requirement, vendor value, points
  earned/lost, weight and a plain-language explanation.
- **Hard vs. soft, strict vs. flexible** — exceeding a flexible budget costs a few points;
  missing a strict, critical deadline triggers a documented penalty. Nobody is silently removed.
- **Deterministic where it matters** — budget, duration, experience and technology are rule-based;
  semantic AI is used only for free-text requirements, as quoted supporting evidence.
- **Private by design** — the language model runs locally inside the container. No external AI APIs,
  no API keys.

## Scoring model

```
effective weight   = explicit weight, or the importance default (Critical 4 · High 3 · Medium 2 · Low 1)
base score         = 100 × Σ normalized_weight × criterion_score            (criterion_score ∈ [0, 1])
overall score      = base score × Π hard-failure multipliers                 (Critical 0.5 · High 0.6 · Medium 0.7 · Low 0.8)
```

| Criterion | How it is scored |
|---|---|
| Budget / duration / experience | Relative deviation `d`. Strict: any deviation → 0. Flexible: `1 − (d/τ)²` (or linear `1 − d/τ`), τ = 25 % by default (5 % over → 0.96, 10 % → 0.84, 20 % → 0.36, ≥ 25 % → 0). Durations in different units are compared in days (1 month = 364/12 days). |
| Technology | Normalized name match against the vendor's stack (`Node`, `node.js`, `NodeJS` are equal). |
| Free text | Semantic similarity (below). |

In the project form users set an **importance** and, optionally, a manual **weight** per requirement.
Penalties there are always graded and scaled by weight: budget uses the quadratic curve (τ 25 %);
deadline and experience use a linear curve, `1 − d/0.5` (1 month late on 12 → 0.83, 3 → 0.50, 6 → 0).
Strict, hard limits with a score multiplier remain available through the API (the demo uses one).
A failed **hard** requirement scores 0 *and* multiplies the overall score; multiple failures compound.
**Soft** gaps only lose their own points. All constants are exposed at `GET /api/scoring-model`.
Neutral labels (*Strong compatibility*, *Mostly compatible with some concerns*, *Requires review*,
*Hard requirement failed*) are presentation only and never change a score.

## Semantic matching

- Model: [`all-MiniLM-L6-v2`](https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2) via
  Sentence Transformers, CPU, baked into the Docker image.
- The requirement text is compared with each sentence of the proposal and previous projects; the
  best sentence is returned verbatim as evidence with its cosine similarity.
- Score ramp: similarity ≤ 0.30 → 0, ≥ 0.60 → 1, linear in between. These are **provisional
  calibration constants**, checked against a fictional 33-pair dataset
  ([results](docs/M2-calibration-results.md)) — not scientifically validated values.
- Isolation: semantic scores only affect `text` criteria and can never override numeric,
  technology or hard requirements.

## Architecture

```
Browser ── vanilla JS SPA (static/) ──► FastAPI (app/api) ──► services ──► repositories ──► SQLite
                                              │
                                              └─► scoring engine (pure functions) ──► semantic matcher ──► local MiniLM
```

```
app/
├── api/          routers, dependency injection, error handlers (one JSON error shape)
├── schemas/      Pydantic models (criteria, projects, vendors, analysis)
├── services/
│   ├── scoring/  numeric, technology, text, aggregation, neutral summaries — no I/O
│   ├── semantic/ embedder interface + sentence-level matcher
│   └── *_service.py  projects, vendors, analysis, demo (transactions, orchestration)
├── data/         sqlite3 connection + repositories (SQL only)
└── main.py       app factory; serves the API and static/ from one process
static/           HTML, CSS, ES modules — no build step, no external assets
examples/         fictional demo project and vendors
tests/            unit · data · API · real-model tests
```

Analyses are **recomputed from current data on every request**; scores are never stored.

## Tech stack

Python 3.12 · FastAPI · Pydantic · SQLite · Sentence Transformers (all-MiniLM-L6-v2, PyTorch CPU) ·
vanilla HTML/CSS/JavaScript · Pytest · Docker · Google Cloud Run · GitHub Actions.
Built with AI-assisted development (Claude Code), milestone by milestone with review at each step.

## Run locally

```bash
python -m venv .venv && source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install --index-url https://download.pytorch.org/whl/cpu torch==2.14.1
pip install -r requirements-dev.txt
uvicorn app.main:app --reload                            # http://localhost:8000
```

Or with Docker:

```bash
docker build -t vendormatch-ai .
docker run -p 8080:8080 vendormatch-ai                  # http://localhost:8080
```

## Testing

```bash
pytest              # 334 tests: scoring, units, criteria, API, persistence, demo, frontend — no model download
pytest -m model     # 7 tests with the real MiniLM model (calibration ordering, demo outcomes)
```

Tests use fake embedders and a temporary SQLite file per test. The GitHub Actions workflow
(`.github/workflows/ci.yml`) runs both suites, builds the Docker image and smoke-tests the running
container (`/api/demo` → 3 vendors).

## Deployment

`scripts/deploy_cloud_run.sh` builds with Cloud Build and deploys to Cloud Run:

```bash
PROJECT_ID=<your-project> ./scripts/deploy_cloud_run.sh
```

Single container, 2 GiB RAM, CPU boost at start-up (the model is preloaded before the first request),
scale to zero, **max one instance** so the per-instance SQLite demo stays consistent. The model is
downloaded at image build time, so the running service never downloads it.

On a new Google Cloud project, Cloud Build may run as the Compute Engine default service account
without any roles; grant it the builder role once before the first deploy:

```bash
gcloud projects add-iam-policy-binding <your-project>   --member=serviceAccount:<project-number>-compute@developer.gserviceaccount.com   --role=roles/cloudbuild.builds.builder
```

## Known limitations

- **Ephemeral demo storage** — SQLite lives in the container's `/tmp`; data resets when the instance
  restarts. Fine for a demo, not for real use.
- **Cold start** — after idle, the first visit waits roughly 40–60 s while the container starts and
  loads the model (the preload alone measured ~37 s on Cloud Run).
- **Semantic matching is approximate** — MiniLM misses negation ("we have *no* e-commerce
  experience" still matches) and can under-rate valid evidence; thresholds are provisional.
- **No authentication** — the public demo is shared: anyone can see projects created there, so it
  must not be used for confidential data.
- **Single currency per project**, no FX conversion.

## Design notes

Milestone design documents: [architecture & scoring](docs/M0-architecture.md) ·
[semantic matching](docs/M2-semantic-matching.md) · [storage & API](docs/M3-storage-api.md) ·
[demo & comparison](docs/M4-demo-and-comparison.md) · [frontend](docs/M5-frontend.md).
