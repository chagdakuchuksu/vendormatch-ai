# M5 — Frontend

Vanilla HTML/CSS/JavaScript (ES modules, no build step, no external assets), served by FastAPI
from `static/` on the same origin as the API. Run `uvicorn app.main:app` and open
`http://localhost:8000/`.

## Structure

```
static/
├── index.html            shell: header (Try Demo), <main id="app">, footer
├── css/styles.css        design tokens, components, responsive rules
└── js/
    ├── app.js            hash router, global actions (Try Demo / retry / refresh), error boundary
    ├── api.js            fetch wrapper → ApiError {status, code, message}
    ├── store.js          per-project cache of project + vendors + comparison + analysis
    ├── ui.js             esc(), formatters, badges, status pills, bars, loading/empty/error states
    └── views/
        ├── home.js       introduction, scoring summary (multipliers from /api/scoring-model), recent projects
        ├── projects.js   project list / empty state
        ├── project.js    overview, requirements, vendor comparison, points-by-criterion matrix
        └── vendor.js     score formula, concerns, criterion breakdown, semantic evidence, proposal
```

Routes: `#/`, `#/projects`, `#/projects/{id}`, `#/projects/{id}/vendors/{vendorId}`. Other hashes
(e.g. `#scoring`) are treated as in-page anchors.

## Rules

- No scoring in JavaScript: every score, status, label, summary and explanation comes from
  `/comparison` or `/analysis`. The frontend only formats (e.g. weight 0.16 → "16%").
- Every API string is HTML-escaped (`esc`) before insertion.
- Neutral wording only; `tests/api/test_frontend.py` scans the static sources and the demo API
  responses for *winner, best, recommend…, choos…, choice, hire…, select…*.
- All vendors are shown with the same layout; ordering follows the backend and is labelled as a
  sorting aid.

## Backend changes required for integration

- `app/main.py`: `StaticFiles` mounted at `/` after all API routers (API routes take precedence;
  unknown `/api/...` paths still return the JSON error shape).
- Text-only wording changes so the UI never shows prohibited words: disclaimer
  ("…the final decision stays with your team"), ordering note ("…a sorting aid, not a decision"),
  semantic explanation prefix ("Matched evidence" instead of "Best evidence"). No scoring change.

## Later additions (after M5)

- Project and vendor-offer forms (`static/js/forms.js`, `views/project-form.js`, `views/vendor-form.js`):
  create / edit / delete, importance and optional weight per requirement.
- Form rules: budget flexible (quadratic, τ 25 %); deadline and experience flexible with a linear
  curve (τ 50 %); written requirements soft. Demo projects keep their original settings when edited.
- In-page "click twice" delete confirmation (browser `confirm()` dialogs can be blocked silently).
- Static files are served with `Cache-Control: no-cache` so redeploys are picked up immediately.
