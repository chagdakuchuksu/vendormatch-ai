# M3 — Storage & API

## Layers

```
app/api/        routers (thin) + deps.py (DI) + error_handlers.py (one JSON error shape)
app/services/   project / vendor / analysis / demo services — validation, transactions, orchestration
app/data/       database.py (sqlite3, schema) + repositories.py (SQL only, Pydantic in/out)
app/services/scoring, app/services/semantic   unchanged M1/M2 engine, no DB or HTTP imports
```

- Repositories never commit; services wrap writes in `with conn:` transactions.
- `app/errors.py` stays framework-free; HTTP mapping lives in `app/api/error_handlers.py`.
- The semantic scorer is injected into `create_app(...)`; production uses MiniLM (lazy-loaded on
  the first analysis that has a text criterion), tests use fake embedders.

## Storage

SQLite (stdlib `sqlite3`), two tables: `projects` and `vendors`. Each row stores the validated
Pydantic document as JSON (projects include their **materialized** criteria with ids, sources and
weights), plus indexed columns for listing. `vendors.project_id` has `ON DELETE CASCADE`.

- Location: `instance/vendormatch.db` by default, `VENDORMATCH_DB_PATH` to override. Created on
  app start-up, never on import.
- **Scores are never stored.** `/analysis` and `/comparison` recompute from current data.
- Cloud Run: the container filesystem is ephemeral — demo data may reset on instance restart.

## Criteria workflow

- `POST /api/projects` → criteria builder adds auto criteria, validates, normalizes weights.
- `PUT /api/projects/{id}` accepts the criteria exactly as `GET` returns them (`CriterionUpdate`):
  `id` and `source` are kept, weight fields are ignored and recomputed. Auto criteria can be edited
  this way. To drop an auto technology criterion, remove the technology from
  `required_technologies` and from `criteria`.
- Invalid criteria → `422 invalid_criteria` / `invalid_weights`; a failed update leaves the stored
  project unchanged.

## Demo

`POST /api/demo` creates a fresh copy of `examples/demo_project.json` + `examples/demo_vendors.json`
(all fictional) in one transaction. Copies are identical and deterministic; only the newest
`VENDORMATCH_MAX_DEMO_PROJECTS` (default 10) demo copies are kept, user projects are never pruned.

## Post-review change: duration units (scoring v1.1)

The M3 end-to-end check showed a vendor proposing **6 months** failing a strict **26-week**
deadline by "0.07 weeks" (4.345 weeks/month). Cross-unit durations are now normalized through
days (1 week = 7 days, 1 month = 364/12 days, exact fractions) — see M0 §3.3. Same-unit scoring is
unchanged (verified on 185 baseline scenarios), as are all formulas and hard-fail multipliers.
The scoring version is bumped to 1.1 because cross-unit results can differ from 1.0.

## Errors

`{"error": {"code", "message", "details"}}` — `validation_error` (422), `invalid_criteria` (422),
`invalid_weights` (422), `not_found` (404), `semantic_model_unavailable` (503).
